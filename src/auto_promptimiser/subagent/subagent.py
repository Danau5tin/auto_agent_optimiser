import logging
import os
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID, uuid4

from auto_promptimiser.core.trajectory_context import TrajectoryContext as TrajectoryContextType

from auto_promptimiser.core.action import Action
from auto_promptimiser.core.base_agent import BaseAgent, ModelConfig
from auto_promptimiser.core.base_parser import BaseParser
from auto_promptimiser.core.trajectory_context import TrajectoryContext
from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from auto_promptimiser.parsers.json_parser import JSONParser
from auto_promptimiser.subagent.config import get_config_for_type
from auto_promptimiser.agent.handlers import HandlerRegistry, FileHandlers, BashHandlers
from auto_promptimiser.agent.actions.finish import FinishAction
from auto_promptimiser.agent.actions.report import ReportAction
from auto_promptimiser.agent.actions.respond import RespondAction
from auto_promptimiser.agent.actions.file_actions import (
    ReadAction,
    WriteAction,
    EditAction,
    MultiEditAction,
)
from auto_promptimiser.agent.actions.bash import BashAction

logger = logging.getLogger(__name__)


@dataclass
class SubAgentTrajectory:
    """Complete trajectory of a subagent run."""
    trajectory_id: UUID
    subagent_type: str
    message_history: list[dict[str, Any]]
    executed_actions: list[type[Action]]



class SubAgent(BaseAgent[Action, TrajectoryContext]):
    """Configurable subagent that can be customized via type parameter.

    The subagent type determines which system message is used.
    Each subagent runs independently with its own conversation history.
    """

    def __init__(
        self,
        subagent_type: str,
        initial_message: str,
        file_manager: Optional[BaseFileManager] = None,
        bash_executor: Optional[BaseBashExecutor] = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize a subagent with a specific type and initial message.

        Args:
            subagent_type: Type identifier for the subagent (e.g., "trajectory_analysis_agent")
            initial_message: The first user message to send to the subagent
            file_manager: Optional file manager for file operations
            bash_executor: Optional bash executor for shell commands
            model: LLM model to use (falls back to LLM_MODEL env var)
            api_key: API key for the LLM (falls back to LLM_API_KEY env var)
        """
        self.subagent_type = subagent_type
        self.model = model or os.getenv("LLM_MODEL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

        if not self.model or not self.api_key:
            raise ValueError("LLM_MODEL and LLM_API_KEY must be set via parameters or environment variables")

        # Get the configuration for this subagent type
        self.config = get_config_for_type(subagent_type)

        # Load the system message from the config
        system_message = self.config.load_system_message()
        super().__init__(system_message=system_message)

        # Setup handler registry with provided dependencies
        self._setup_handler_registry(file_manager, bash_executor)

        # Initialize context tracking (set during run())
        self._context: Optional[TrajectoryContextType] = None
        self._trajectory_id: Optional[UUID] = None

        # Add the initial message to start the conversation
        self.add_user_message(initial_message)

        logger.info(f"Initialized {subagent_type} subagent")

    def _setup_handler_registry(
        self,
        file_manager: Optional[BaseFileManager],
        bash_executor: Optional[BaseBashExecutor],
    ) -> None:
        """Setup handler registry based on available dependencies.

        Only registers handlers for actions that:
        1. Are in the subagent's available_action_map
        2. Have the required dependencies available
        """

        self.handler_registry = HandlerRegistry()

        available_actions = set(self.config.available_action_map.values())

        # Register file handlers if file_manager is provided
        if file_manager:
            file_handlers = FileHandlers(file_manager)
            if ReadAction in available_actions:
                self.handler_registry.register(ReadAction, file_handlers.handle_read)
            if WriteAction in available_actions:
                self.handler_registry.register(WriteAction, file_handlers.handle_write)
            if EditAction in available_actions:
                self.handler_registry.register(EditAction, file_handlers.handle_edit)
            if MultiEditAction in available_actions:
                self.handler_registry.register(MultiEditAction, file_handlers.handle_multi_edit)

        # Register bash handler if bash_executor is provided
        if bash_executor and BashAction in available_actions:
            bash_handlers = BashHandlers(bash_executor)
            self.handler_registry.register(BashAction, bash_handlers.handle_bash)

    def _setup_action_parser(self) -> BaseParser[Action]:
        return JSONParser[Action](
            mapping_tag_to_action_class=self.config.available_action_map
        )

    def _get_model_config(self) -> ModelConfig:
        return ModelConfig(model=self.model, api_key=self.api_key)

    async def _execute_action(
        self, action: Action, context: TrajectoryContext
    ) -> tuple[str, bool]:
        """Execute actions for the subagent using the handler registry.

        Subagents can execute actions based on their configuration and available dependencies.
        """
        context.executed_actions.append(type(action))

        # Handle termination actions - they signal the conversation should pause
        if isinstance(action, (FinishAction, ReportAction, RespondAction)):
            context.is_finished = True
            return "", False

        # Use the handler registry to execute the action
        formatted_response, is_error = await self.handler_registry.handle(action, context)
        return formatted_response, is_error

    async def run(self) -> SubAgentTrajectory:
        """Run the subagent and return its complete trajectory.

        Returns:
            SubAgentTrajectory containing the full message history and execution details
        """
        trajectory_id = uuid4()
        self._context = TrajectoryContext(trajectory_id=trajectory_id)
        self._trajectory_id = trajectory_id

        logger.info(f"Running {self.subagent_type} subagent: {trajectory_id}")

        await self._run_until_finished()

        return self._build_trajectory()

    async def continue_with_message(self, message: str) -> SubAgentTrajectory:
        """Continue the subagent conversation with a new user message.

        Use this to send follow-up messages after run() has completed,
        for example to request a valid report if none was provided.

        Args:
            message: The user message to send to the subagent

        Returns:
            SubAgentTrajectory containing the updated message history
        """
        if self._context is None or self._trajectory_id is None:
            raise RuntimeError("Cannot continue: subagent has not been run yet. Call run() first.")

        # Reset finished state to allow continued processing
        self._context.is_finished = False

        # Add the new message and continue
        self.add_user_message(message)

        logger.info(f"Continuing {self.subagent_type} subagent: {self._trajectory_id}")

        await self._run_until_finished()

        return self._build_trajectory()

    async def _run_until_finished(self) -> None:
        """Run the agent loop until finished."""
        while True:
            should_terminate = await self.process_llm_turn(self._context)

            if should_terminate:
                logger.info(f"{self.subagent_type} subagent completed: {self._trajectory_id}")
                break

    def _build_trajectory(self) -> SubAgentTrajectory:
        """Build and return the current trajectory."""
        return SubAgentTrajectory(
            trajectory_id=self._trajectory_id,
            subagent_type=self.subagent_type,
            message_history=self.message_history.copy(),
            executed_actions=self._context.executed_actions.copy(),
        )

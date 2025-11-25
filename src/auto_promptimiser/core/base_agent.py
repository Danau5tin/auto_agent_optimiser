from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, TypeVar
import logging

from auto_promptimiser.core.trajectory_context import TrajectoryContext
from auto_promptimiser.core.base_parser import BaseParser
from auto_promptimiser.core.action import Action
from auto_promptimiser.misc.llm_client import get_llm_response

logger = logging.getLogger(__name__)

TAction = TypeVar("TAction", bound=Action)
TContext = TypeVar("TContext", bound=TrajectoryContext)


@dataclass
class ModelConfig:
    model: str
    api_key: str

class BaseAgent(ABC, Generic[TAction, TContext]):
    """Base class for LLM agents that use action parsing.

    Provides common functionality for:
    - Message history management
    - LLM interaction loop
    - Action parsing workflow

    Subclasses must implement action mapping, execution logic, and termination conditions.
    """

    def __init__(self, system_message: str):
        self.message_history: List[Dict[str, str]] = [
            {"role": "system", "content": system_message}
        ]
        self.tool_parser = self._setup_action_parser()

    @abstractmethod
    def _setup_action_parser(self) -> BaseParser[TAction]:
        """Configure and return the action parser with action mappings.

        Returns:
            BaseParser (XmlYamlParser, JSONParser, etc.) configured with action class mappings

        Example:
            return XmlYamlParser[Action](
                mapping_tag_to_action_class={
                    "bash": BashAction,
                    "read": ReadAction,
                },
                ignored_tags=["think"]
            )
        """
        pass

    @abstractmethod
    async def _execute_action(
        self, action: TAction, context: TContext
    ) -> tuple[str, bool]:
        """Execute a single action and return the result.

        Args:
            action: The parsed action to execute
            context: Execution context (run metadata, state, etc.)

        Returns:
            tuple of (formatted_response, is_error)
        """
        pass

    def _should_terminate(self, context: TContext) -> bool:
        """Check if the agent should stop processing.

        Args:
            context: Current execution context

        Returns:
            True if agent should terminate, False otherwise
        """
        return context.is_finished

    @abstractmethod
    def _get_model_config(self) -> ModelConfig:
        """Get LLM configuration (model, api_key, etc.).

        Returns:
            ModelConfig with LLM settings
        """
        pass

    async def process_llm_turn(self, context: TContext) -> bool:
        """Process a single LLM interaction turn.

        Args:
            context: Execution context for this turn

        Returns:
            True if should terminate, False to continue
        """
        llm_config = self._get_model_config()
        logger.debug("Requesting LLM response")

        llm_resp = await get_llm_response(
            messages=self.message_history,
            model=llm_config.model,
            api_key=llm_config.api_key,
        )
        self.message_history.append({"role": "assistant", "content": llm_resp})

        logger.debug("Parsing actions from LLM response")
        actions, errors, found_action_attempt = self.tool_parser.parse_actions(
            response=llm_resp
        )

        env_response = ""

        if not found_action_attempt:
            env_response += "No valid actions found in the LLM response.\n"

        if errors:
            env_response += "Errors encountered while parsing actions:\n"
            for error in errors:
                env_response += f"- {error}\n"

        logger.info(f"Action types: {[type(a).__name__ for a in actions]} parsed.")

        for action in actions:
            logger.debug(f"Executing action: {type(action).__name__}")

            # Allow subclass to handle action execution logic
            formatted_response, is_error = await self._execute_action(action, context)
            env_response += formatted_response + "\n"

            # Check termination after each action
            if self._should_terminate(context):
                return True

        if env_response.strip():
            self.message_history.append({"role": "user", "content": env_response})

        return False

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self.message_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the history."""
        self.message_history.append({"role": "assistant", "content": content})

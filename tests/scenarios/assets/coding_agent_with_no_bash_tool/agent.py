import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List

from harbor import AgentContext, BaseEnvironment
from harbor.agents.base import BaseAgent
from harbor.models.trajectories import (
    Agent,
    FinalMetrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall as TrajectoryToolCall,
    Trajectory,
)
from auto_promptimiser.misc.llm_client import get_llm_response
from auto_promptimiser.parsers.json_parser import JSONParser
from .tool_call_entities import (
    FileEditToolCall,
    FileReadToolCall,
    FileWriteToolCall,
    FinishToolCall,
    ToolCall,
)
from .file_system_tool_handler import FileSystemToolHandler


SYSTEM_PROMPT = """You are a coding assistant that can read and edit files.

To read a file, use:
{
  "action_type": "file_read",
  "file_path": "path/to/file.py"
}

To edit a file, use:
{
  "action_type": "file_edit",
  "file_path": "path/to/file.py",
  "old_content": "# exact content to replace\\ndef old_function():\\n    pass",
  "new_content": "# new content\\ndef new_function():\\n    return True"
}

To write a new file, use:
{
  "action_type": "file_write",
  "file_path": "path/to/new_file.py",
  "content": "# file contents\\ndef my_function():\\n    return True"
}

To finish the task, use:
{
  "action_type": "finish",
  "message": "Task completed successfully."
}

You can provide multiple actions in a JSON array:
[
  {"action_type": "file_read", "file_path": "file1.py"},
  {"action_type": "file_read", "file_path": "file2.py"}
]

When you're done with the task, respond without any tool calls to indicate completion."""


class CodingAgent(BaseAgent):
    def __init__(
        self, max_turns: int = 15, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.tool_call_parser = JSONParser[ToolCall](
            mapping_tag_to_action_class={
                "file_read": FileReadToolCall,
                "file_edit": FileEditToolCall,
                "file_write": FileWriteToolCall,
                "finish": FinishToolCall,
            }
        )
        self.max_turns = max_turns
        self.messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.session_id = str(uuid.uuid4())
        self.trajectory_steps: List[Step] = []
        self.model_name = os.getenv("CODING_LLM_MODEL")
        self.model_api_key = os.getenv("CODING_LLM_API_KEY")
        if not self.model_name or not self.model_api_key:
            raise ValueError(
                "CODING_LLM_MODEL and CODING_LLM_API_KEY environment variables must be set."
            )
        self.file_system_handler: FileSystemToolHandler | None = None

    @staticmethod
    def name() -> str:
        return "coding_agent"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        self.file_system_handler = FileSystemToolHandler(environment)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """
        Runs the agent in the environment. Be sure to populate the context with the
        results of the agent execution. Ideally, populate the context as the agent
        executes in case of a timeout or other error.

        Args:
            instruction: The task instruction.
            environment: The environment in which to complete the task.
            context: The context to populate with the results of the agent execution.
        """
        # Add system message as step 1
        self.trajectory_steps.append(
            Step(
                step_id=1,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="system",
                message=SYSTEM_PROMPT,
            )
        )

        # Add user instruction as step 2
        self.trajectory_steps.append(
            Step(
                step_id=2,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="user",
                message=instruction,
            )
        )

        turns = 0
        self.messages.append({"role": "user", "content": instruction})

        try:
            while turns < self.max_turns:
                turns += 1

                resp = await get_llm_response(
                    messages=self.messages,
                    model=self.model_name,
                    api_key=self.model_api_key,
                )
                self.messages.append({"role": "assistant", "content": resp})

                actions, errors, found_action_attempt = (
                    self.tool_call_parser.parse_actions(resp)
                )

                tool_calls = self._create_trajectory_tool_calls(actions, turns)

                # Check if finish action was called
                has_finish = any(isinstance(action, FinishToolCall) for action in actions)

                if not found_action_attempt:
                    # Final response with no tool calls
                    self.trajectory_steps.append(
                        Step(
                            step_id=len(self.trajectory_steps) + 1,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            source="agent",
                            model_name=self.model_name,
                            message=resp,
                        )
                    )
                    break

                observation_results = await self._execute_actions_with_observations(
                    actions, errors, tool_calls
                )

                self.trajectory_steps.append(
                    Step(
                        step_id=len(self.trajectory_steps) + 1,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        source="agent",
                        model_name=self.model_name,
                        message=resp,
                        tool_calls=tool_calls if tool_calls else None,
                        observation=Observation(results=observation_results)
                        if observation_results
                        else None,
                    )
                )

                user_msg_content = f"<results>\n{observation_results}\n</results>"
                self.messages.append(
                    {"role": "user", "content": user_msg_content}
                )

                # Add user step acknowledging the results (without observation - that's on the agent step)
                self.trajectory_steps.append(
                    Step(
                        step_id=len(self.trajectory_steps) + 1,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        source="user",
                        message=user_msg_content,
                    )
                )

                # Break the loop if finish action was called
                if has_finish:
                    break
            else:
                # Max turns reached - add a user message explaining this
                max_turns_msg = f"Maximum turns ({self.max_turns}) reached. Task execution stopped."
                self.trajectory_steps.append(
                    Step(
                        step_id=len(self.trajectory_steps) + 1,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        source="user",
                        message=max_turns_msg,
                    )
                )

        except Exception as e:
            context.metadata = {
                "error": f"Agent execution error: {str(e)}",
            }

        finally:
            context.metadata = context.metadata or {}
            context.metadata.update(
                {
                    "trajectory_path": str(self.logs_dir / "trajectory.json"),
                    "session_id": self.session_id,
                    "turns": turns,
                    "max_turns": self.max_turns,
                }
            )
            self._dump_trajectory(context) 

    def _create_trajectory_tool_calls(
        self, actions: List[ToolCall], turn: int
    ) -> List[TrajectoryToolCall] | None:
        if not actions:
            return None

        tool_calls = []
        for i, action in enumerate(actions):
            tool_call_id = f"call_{turn}_{i + 1}"
            tool_calls.append(
                TrajectoryToolCall(
                    tool_call_id=tool_call_id,
                    function_name=action.__class__.__name__,
                    arguments=action.model_dump(),
                )
            )
        return tool_calls if tool_calls else None

    async def _execute_actions_with_observations(
        self,
        actions: List[ToolCall],
        errors: List[str],
        tool_calls: List[TrajectoryToolCall] | None,
    ) -> List[ObservationResult]:
        if not self.file_system_handler:
            raise RuntimeError("File system handler is not initialized.")
        
        observation_results = []

        for i, action in enumerate(actions):
            tool_call_id = (
                tool_calls[i].tool_call_id
                if tool_calls and i < len(tool_calls)
                else None
            )
            response = ""

            if isinstance(action, FileReadToolCall):
                response = await self.file_system_handler.read_file(
                    file_path=action.file_path,
                )
            elif isinstance(action, FileEditToolCall):
                response = await self.file_system_handler.edit_file(
                    file_path=action.file_path,
                    old_content=action.old_content,
                    new_content=action.new_content,
                )
            elif isinstance(action, FileWriteToolCall):
                response = await self.file_system_handler.write_file(
                    file_path=action.file_path,
                    content=action.content,
                )
            elif isinstance(action, FinishToolCall):
                response = f"Task finished: {action.message}"

            observation_results.append(
                ObservationResult(source_call_id=tool_call_id, content=response)
            )

        # Add errors as observations without source_call_id
        for error in errors:
            observation_results.append(
                ObservationResult(
                    source_call_id=None,
                    content=f"Error: {error}",
                )
            )

        return observation_results

    def _dump_trajectory(self, context: AgentContext | None = None) -> None:
        """Dump trajectory data to JSON file following ATIF format."""
        trajectory = Trajectory(
            session_id=self.session_id,
            agent=Agent(
                name=self.name(),
                version=self.version() or "unknown",
                model_name=self.model_name,
            ),
            steps=self.trajectory_steps,
            final_metrics=FinalMetrics(),
            extra=context.metadata if context and context.metadata else {},
        )

        trajectory_path = self.logs_dir / "trajectory.json"
        try:
            with open(trajectory_path, "w", encoding="utf-8") as f:
                json.dump(trajectory.to_json_dict(), f, indent=2)
            self.logger.debug(f"Trajectory dumped to {trajectory_path}")
        except Exception as e:
            self.logger.error(f"Failed to dump trajectory: {e}")

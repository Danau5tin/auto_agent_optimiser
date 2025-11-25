"""Handlers for sub-agent related actions."""

from typing import Tuple
from auto_promptimiser.agent.actions.subagent_actions import (
    DispatchTrajAnalysisAgentAction,
    SendSubagentMessageAction,
)
from auto_promptimiser.agent.actions.report import ReportAction
from auto_promptimiser.agent.actions.respond import RespondAction
from auto_promptimiser.agent.handlers.registry import HandlerContext
from auto_promptimiser.agent.handlers.utils import format_tool_output
from auto_promptimiser.core.base_eval_storage import BaseEvalStorage
from auto_promptimiser.core.project_breakdown import ProjectBreakdown
from auto_promptimiser.subagent.subagent import SubAgent
from auto_promptimiser.subagent.manager import SubAgentManager
from auto_promptimiser.parsers.json_parser import JSONParser

TRAJ_ANA_SUBAGENT_TYPE = "trajectory_analysis_agent"

REPORT_REQUIRED_MESSAGE = (
    "Your response did not include a valid report action. "
    "Please provide your analysis using the report action format. "
    "This is required to complete your task and the syntax must be as described within your system message: <report>...</report>"
)


class SubAgentHandlers:
    """Handlers for sub-agent dispatch actions.

    This class groups all sub-agent operation handlers together since they
    share dependencies related to running sub-agents.
    """

    def __init__(
        self,
        eval_storage: BaseEvalStorage,
        model: str,
        api_key: str,
        project_breakdown: ProjectBreakdown,
        subagent_manager: SubAgentManager,
    ):
        self.eval_storage = eval_storage
        self.model = model
        self.api_key = api_key
        self.project_breakdown = project_breakdown
        self.subagent_manager = subagent_manager

    async def handle_dispatch_traj_analysis_agent(
        self, action: DispatchTrajAnalysisAgentAction, context: HandlerContext
    ) -> Tuple[str, bool]:
        """Dispatch and run a trajectory analysis agent, returning its report.

        Args:
            action: The dispatch action containing initial message and eval ID
            context: The handler context

        Returns:
            Tuple of (formatted output, is_error)
        """
        try:
            # Load the evaluation results for the specified iteration
            eval_results = await self.eval_storage.get_iteration_results(
                context.trajectory_id, action.iteration_number
            )

            if eval_results is None:
                return (
                    format_tool_output(
                        "dispatch_traj_analysis_agent",
                        f"No evaluation results found for iteration {action.iteration_number}",
                    ),
                    True,
                )

            # Find the specific eval by name
            target_eval = None
            for eval_result in eval_results:
                if eval_result.eval_name == action.eval_name:
                    target_eval = eval_result
                    break

            if target_eval is None:
                return (
                    format_tool_output(
                        "dispatch_traj_analysis_agent",
                        f"No evaluation found with name '{action.eval_name}' in iteration {action.iteration_number}",
                    ),
                    True,
                )

            # Find the specific attempt
            target_attempt = None
            for attempt in target_eval.attempts:
                if attempt.attempt_number == action.attempt_number:
                    target_attempt = attempt
                    break

            if target_attempt is None:
                 return (
                    format_tool_output(
                        "dispatch_traj_analysis_agent",
                        f"No attempt found with number {action.attempt_number} for eval '{action.eval_name}' in iteration {action.iteration_number}. Available attempts: {[a.attempt_number for a in target_eval.attempts]}",
                    ),
                    True,
                )

            # Extract the trajectory from the eval attempt without the system message
            eval_trajectory = target_attempt.trajectory
            if eval_trajectory[0]["source"] == "system":
                eval_trajectory = eval_trajectory[1:]


            # Convert trajectory to string and append to initial message
            trajectory_str = str(eval_trajectory)
            full_initial_message = (
                f"# Initial message\n"
                f"{action.initial_message}\n\n"
                f"# Agent's available actions\n"
                f"{self.project_breakdown.actions_to_str()}\n\n"
                f"# Evaluation trajectory (Attempt {action.attempt_number}):\n"
                f"```\n"
                f"{trajectory_str}\n"
                f"```"
            )

            # Create and run the sub-agent
            subagent = SubAgent(
                subagent_type=TRAJ_ANA_SUBAGENT_TYPE,
                initial_message=full_initial_message,
                model=self.model,
                api_key=self.api_key,
            )

            trajectory = await subagent.run()

            # Extract the report from the trajectory
            report_message = self._extract_report(trajectory.message_history)

            # If no report found, send a follow-up message requesting one
            if report_message is None:
                trajectory = await subagent.continue_with_message(REPORT_REQUIRED_MESSAGE)
                report_message = self._extract_report(trajectory.message_history)

            if report_message is None:
                return (
                    format_tool_output(
                        "dispatch_traj_analysis_agent",
                        f"Trajectory analysis agent completed but did not provide a report after retry",
                    ),
                    True,
                )

            # Register the subagent so it can receive follow-up messages
            subagent_id = self.subagent_manager.register(subagent)

            return (
                format_tool_output(
                    "dispatch_traj_analysis_agent",
                    f"Subagent ID: {subagent_id}\n\n"
                    f"Trajectory analysis agent report:\n\n{report_message}",
                ),
                False,
            )

        except Exception as e:
            error_message = f"Error dispatching trajectory analysis agent: {str(e)}"
            return format_tool_output(
                "dispatch_traj_analysis_agent", error_message
            ), True

    async def handle_send_subagent_message(
        self, action: SendSubagentMessageAction, context: HandlerContext
    ) -> Tuple[str, bool]:
        """Send a follow-up message to an active subagent.

        Args:
            action: The action containing the subagent ID and message
            context: The handler context

        Returns:
            Tuple of (formatted output, is_error)
        """
        try:
            subagent = self.subagent_manager.get(action.subagent_id)

            if subagent is None:
                active_ids = self.subagent_manager.list_active_ids()
                return (
                    format_tool_output(
                        "send_subagent_message",
                        f"No active subagent found with ID '{action.subagent_id}'. "
                        f"Active subagent IDs: {active_ids if active_ids else 'none'}",
                    ),
                    True,
                )

            # Send the message and get the response
            trajectory = await subagent.continue_with_message(action.message)

            # Extract the response (can be either RespondAction or ReportAction)
            response_message = self._extract_response(trajectory.message_history)

            if response_message is None:
                return (
                    format_tool_output(
                        "send_subagent_message",
                        f"Subagent did not provide a valid response. "
                        f"The subagent should use the 'respond' or 'report' action.",
                    ),
                    True,
                )

            return (
                format_tool_output(
                    "send_subagent_message",
                    f"Subagent ({action.subagent_id}) response:\n\n{response_message}",
                ),
                False,
            )

        except Exception as e:
            error_message = f"Error sending message to subagent: {str(e)}"
            return format_tool_output("send_subagent_message", error_message), True

    def _extract_report(self, message_history: list[dict]) -> str | None:
        """Extract the report message from the sub-agent's message history.

        Looks for the last assistant message that contains a ReportAction.

        Args:
            message_history: The message history from the sub-agent

        Returns:
            The report message if found, None otherwise
        """
        # Iterate through messages in reverse to find the most recent report
        for message in reversed(message_history):
            if message.get("role") != "assistant":
                continue

            content = message.get("content", "")
            if not content:
                continue

            # Try to parse the content as JSON to find ReportAction
            try:
                parser = JSONParser(
                    mapping_tag_to_action_class={"report": ReportAction}
                )
                actions, errors, found_action = parser.parse_actions(content)

                # Find the report action
                for parsed_action in actions:
                    if isinstance(parsed_action, ReportAction):
                        return parsed_action.message

            except Exception:
                # If parsing fails, continue to next message
                continue

        return None

    def _extract_response(self, message_history: list[dict]) -> str | None:
        """Extract the response message from the sub-agent's message history.

        Looks for the last assistant message that contains a RespondAction or ReportAction.

        Args:
            message_history: The message history from the sub-agent

        Returns:
            The response message if found, None otherwise
        """
        for message in reversed(message_history):
            if message.get("role") != "assistant":
                continue

            content = message.get("content", "")
            if not content:
                continue

            try:
                parser = JSONParser(
                    mapping_tag_to_action_class={
                        "respond": RespondAction,
                        "report": ReportAction,
                    }
                )
                actions, errors, found_action = parser.parse_actions(content)

                for parsed_action in actions:
                    if isinstance(parsed_action, RespondAction):
                        return parsed_action.message
                    if isinstance(parsed_action, ReportAction):
                        return parsed_action.message

            except Exception:
                continue

        return None

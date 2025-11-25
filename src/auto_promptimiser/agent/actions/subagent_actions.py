from auto_promptimiser.core.action import Action
from pydantic import Field


class DispatchTrajAnalysisAgentAction(Action):
    """Dispatches a trajectory analysis agent to analyze a specific evaluation."""
    initial_message: str = Field(..., min_length=1, description="Context about the target system and evaluation task")
    iteration_number: int = Field(..., ge=0, description="Iteration number of the evaluation to analyze")
    eval_name: str = Field(..., min_length=1, description="Name of the specific evaluation to analyze")
    attempt_number: int = Field(default=1, ge=1, description="The specific attempt number to analyze (1-based index).")


class SendSubagentMessageAction(Action):
    """Sends a follow-up message to an active subagent and receives its response.

    Use this to ask clarifying questions or request additional analysis from
    a subagent that was previously dispatched. The subagent must still be active
    (not disposed by end_iteration).
    """
    subagent_id: str = Field(..., min_length=1, description="The ID of the subagent to message (returned from dispatch)")
    message: str = Field(..., min_length=1, description="The message to send to the subagent")

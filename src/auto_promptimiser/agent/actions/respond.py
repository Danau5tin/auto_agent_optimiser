from auto_promptimiser.core.action import Action
from pydantic import Field


class RespondAction(Action):
    """Used by subagents to respond to follow-up messages from the parent agent.

    Unlike ReportAction which signals task completion, RespondAction allows
    the subagent to answer questions while remaining available for further dialogue.
    """
    message: str = Field(..., min_length=1, description="Response message to the parent agent")

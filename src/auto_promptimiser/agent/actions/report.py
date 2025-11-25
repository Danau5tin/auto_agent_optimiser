from auto_promptimiser.core.action import Action
from pydantic import Field


class ReportAction(Action):
    """Indicates the agent has completed its task."""
    message: str = Field(..., min_length=1, description="Report message from the agent")
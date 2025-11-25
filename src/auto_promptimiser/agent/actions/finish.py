from auto_promptimiser.core.action import Action
from pydantic import Field


class FinishAction(Action):
    """Indicates the agent has completed its task."""
    message: str = Field(..., min_length=1, description="Final message from the agent")
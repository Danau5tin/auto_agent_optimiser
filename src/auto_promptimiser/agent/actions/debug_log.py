from pydantic import Field

from auto_promptimiser.core.action import Action


class DebugLogAction(Action):
    """Logs a debug message explaining what the agent is doing and why."""
    message: str = Field(..., min_length=1, description="Concise explanation of current actions")

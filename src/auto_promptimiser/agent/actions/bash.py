from auto_promptimiser.core.action import Action
from pydantic import Field


class BashAction(Action):
    """Execute a bash command."""

    cmd: str = Field(..., min_length=1, description="Command to execute")
    block: bool = Field(True, description="Wait for command to complete")
    timeout_secs: int = Field(1, gt=0, le=300, description="Timeout in seconds")
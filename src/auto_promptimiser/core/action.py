from pydantic import BaseModel, ConfigDict


class Action(BaseModel):
    """Base action class using Pydantic for validation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
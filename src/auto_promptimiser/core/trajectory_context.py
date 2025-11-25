"""Base context for agent execution."""

from dataclasses import dataclass, field
from typing import Type
from uuid import UUID

from auto_promptimiser.core.action import Action


@dataclass
class TrajectoryContext:
    """Base context shared across all agents."""
    trajectory_id: UUID
    executed_actions: list[Type[Action]] = field(default_factory=list)
    is_finished: bool = False

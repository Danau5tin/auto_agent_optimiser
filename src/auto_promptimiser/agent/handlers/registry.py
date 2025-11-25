"""Registry for mapping action types to handlers."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Tuple, Type, TypeVar
from auto_promptimiser.agent.actions.file_actions import Action
from auto_promptimiser.agent.handlers.utils import format_tool_output
from auto_promptimiser.core.trajectory_context import TrajectoryContext
from auto_promptimiser.core.eval_entities import IterationHistoryEntry

T = TypeVar("T", bound=Action)


@dataclass
class HandlerContext(TrajectoryContext):
    """Context passed to all action handlers.

    Extends BaseContext with iteration tracking specific to the optimiser agent.
    """
    iteration: int = 0
    should_collapse_context: bool = False
    iteration_history_entry: IterationHistoryEntry | None = None


class HandlerRegistry:
    """Registry for mapping action types to their handlers.

    This class maintains a dictionary mapping action types to handler functions,
    and provides a unified interface for executing actions.
    """

    def __init__(self):
        """Initialize an empty handler registry."""
        self._handlers: dict[
            Type[Action], Callable[[Any, TrajectoryContext], Awaitable[Tuple[str, bool]]]
        ] = {}

    def register(
        self,
        action_type: Type[T],
        handler: Callable[[T, TrajectoryContext], Awaitable[Tuple[str, bool]]],
    ) -> None:
        self._handlers[action_type] = handler  # type: ignore[assignment]

    async def handle(
        self, action: Action, context: TrajectoryContext
    ) -> Tuple[str, bool]:
        """
        Handle the given action using its registered handler.
        
        Returns:
            A tuple containing the formatted output string and a boolean indicating if there was an error.
        """
        handler = self._handlers.get(type(action))
        if not handler:
            content = f"[ERROR] Unknown action type: {type(action).__name__}"
            return format_tool_output("unknown", content), True

        return await handler(action, context)

    def is_registered(self, action_type: Type[Action]) -> bool:
        return action_type in self._handlers

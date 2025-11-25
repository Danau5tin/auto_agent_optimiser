"""Base protocol for action handlers."""

from typing import Awaitable, Protocol, Tuple
from auto_promptimiser.agent.actions.file_actions import Action


class ActionHandler(Protocol):
    """Protocol for action handlers.

    Handlers process actions and return formatted responses.
    """

    def __call__(self, action: Action) -> Awaitable[Tuple[str, bool]]:
        """Handle an action.

        Args:
            action: The action to handle

        Returns:
            Awaitable that resolves to tuple of (formatted_response, is_error)
        """
        ...

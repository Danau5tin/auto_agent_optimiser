from abc import ABC, abstractmethod
from uuid import UUID


class BaseMessageStorage(ABC):
    """Abstract base class for storing and retrieving agent message history."""

    @abstractmethod
    async def store_messages(
        self,
        run_id: UUID,
        messages: list[dict]
    ) -> None:
        """Store message history for a specific run."""
        pass

    @abstractmethod
    async def get_messages(self, run_id: UUID) -> list[dict] | None:
        """Retrieve message history for a given run. Returns None if not found."""
        pass

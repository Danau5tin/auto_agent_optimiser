from abc import ABC, abstractmethod
from uuid import UUID
from auto_promptimiser.core.eval_entities import EvalResult

class BaseEvalStorage(ABC):
    """Abstract base class for storing and retrieving evaluation results."""

    @abstractmethod
    async def store_iteration_results(
        self,
        run_id: UUID,
        iteration_number: int,
        results: list[EvalResult]
    ) -> None:
        """Store evaluation results for a specific iteration."""
        pass

    @abstractmethod
    async def get_run_results(self, optimise_run_id: UUID) -> list[tuple[int, list[EvalResult]]]:
        """Retrieve all results for a given optimisation run. Returns list of (iteration_number, results) tuples."""
        pass

    @abstractmethod
    async def get_iteration_results(self, optimise_run_id: UUID, iteration_number: int) -> list[EvalResult] | None:
        """Retrieve results for a specific iteration. Returns None if not found."""
        pass

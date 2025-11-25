from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from auto_promptimiser.core.eval_entities import EvalSuiteResult


@dataclass
class IterationMetrics:
    """Metrics captured at the end of each iteration (including iteration 0 for initial evals)."""
    run_id: UUID
    iteration_number: int
    changelog: str | None  # None for initial eval (iteration 0)
    eval_result: EvalSuiteResult

    @property
    def accuracy(self) -> float:
        """Shorthand for getting accuracy percentage."""
        return self.eval_result.summarise().accuracy

    @property
    def num_correct(self) -> int:
        """Number of passing evals."""
        return self.eval_result.summarise().num_correct

    @property
    def total_evals(self) -> int:
        """Total number of evals."""
        return self.eval_result.summarise().total

    @property
    def average_score(self) -> float:
        """Average score across all evals (0-1 range)."""
        return self.eval_result.summarise().average_score


class BaseMonitor(ABC):
    """Abstract base class for monitoring optimization progress."""

    @abstractmethod
    def on_optimization_start(self, run_id: UUID) -> None:
        """Called when optimization begins."""
        pass

    @abstractmethod
    def on_iteration_start(self, run_id: UUID, iteration_number: int) -> None:
        """Called at the start of each iteration."""
        pass

    @abstractmethod
    def on_iteration_complete(self, metrics: IterationMetrics) -> None:
        """Called when an iteration completes with eval results."""
        pass

    @abstractmethod
    def on_optimization_complete(self, run_id: UUID, final_iteration: int) -> None:
        """Called when optimization finishes."""
        pass

    @abstractmethod
    def on_error(self, run_id: UUID, iteration_number: int, error: Exception) -> None:
        """Called when an error occurs."""
        pass

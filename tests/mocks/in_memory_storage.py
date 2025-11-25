"""In-memory storage implementations for testing."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from auto_promptimiser.core.base_eval_storage import BaseEvalStorage
from auto_promptimiser.core.base_message_storage import BaseMessageStorage
from auto_promptimiser.core.eval_entities import EvalResult


class InMemoryEvalStorage(BaseEvalStorage):
    """In-memory evaluation storage for testing."""

    def __init__(self):
        # Maps (run_id, iteration) -> list of EvalResult
        self.results: Dict[str, List[EvalResult]] = {}

    async def store_iteration_results(
        self,
        run_id: UUID,
        iteration_number: int,
        results: List[EvalResult]
    ) -> None:
        key = f"{run_id}_{iteration_number}"
        self.results[key] = results

    async def get_run_results(self, optimise_run_id: UUID) -> List[tuple[int, List[EvalResult]]]:
        """Retrieve all results for a given optimisation run."""
        run_results = []
        prefix = str(optimise_run_id)
        for key, results in self.results.items():
            if key.startswith(prefix):
                # Extract iteration number from key
                iteration = int(key.split("_")[-1])
                run_results.append((iteration, results))
        # Sort by iteration number
        run_results.sort(key=lambda x: x[0])
        return run_results

    async def get_iteration_results(
        self,
        optimise_run_id: UUID,
        iteration_number: int
    ) -> Optional[List[EvalResult]]:
        key = f"{optimise_run_id}_{iteration_number}"
        return self.results.get(key)


class InMemoryMessageStorage(BaseMessageStorage):
    """In-memory message storage for testing."""

    def __init__(self):
        self.messages: Dict[UUID, List[Dict[str, Any]]] = {}

    async def store_messages(
        self,
        run_id: UUID,
        messages: List[Dict[str, Any]]
    ) -> None:
        self.messages[run_id] = messages

    async def get_messages(self, run_id: UUID) -> Optional[List[Dict[str, Any]]]:
        return self.messages.get(run_id)

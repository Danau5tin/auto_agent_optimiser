from uuid import UUID
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
from auto_promptimiser.core.base_eval_storage import BaseEvalStorage
from auto_promptimiser.core.eval_entities import EvalResult, EvalAttempt
from tinydb import TinyDB, Query

class NoSQLEvalStorage(BaseEvalStorage):
    """TinyDB-based NoSQL implementation of eval result storage.

    Stores each eval execution independently with a timestamp, allowing multiple
    runs of the same eval within an iteration.
    """

    def __init__(self, db_path: str = "eval_results.json"):
        """
        Initialize the NoSQL storage.

        Args:
            db_path: Path to the TinyDB JSON file. Defaults to "eval_results.json"
        """
        self.db_path = Path(db_path)
        self.db = TinyDB(self.db_path)
        self.table = self.db.table('eval_results')

    def _reconstruct_eval_result(self, result_dict: dict) -> EvalResult:
        """Reconstruct EvalResult from dictionary, handling nested EvalAttempt objects."""
        attempts_data = result_dict.get('attempts', [])
        attempts = [EvalAttempt(**attempt_data) for attempt_data in attempts_data]
        
        # Create a copy of dict to avoid modifying the original
        kwargs = result_dict.copy()
        kwargs['attempts'] = attempts
        
        return EvalResult(**kwargs)

    async def store_iteration_results(
        self,
        run_id: UUID,
        iteration_number: int,
        results: list[EvalResult]
    ) -> None:
        """Store evaluation results for a specific iteration.

        Each eval result is stored as a separate document with a timestamp.
        """
        timestamp = datetime.utcnow().isoformat()

        # Store each eval result as a separate document
        for result in results:
            document = {
                'optimise_run_id': str(run_id),
                'iteration_number': iteration_number,
                'eval_name': result.eval_name,
                'timestamp': timestamp,
                'result': asdict(result)
            }
            self.table.insert(document)

    async def get_run_results(self, optimise_run_id: UUID) -> list[tuple[int, list[EvalResult]]]:
        """Retrieve all results for a given optimisation run.

        Returns list of (iteration_number, results) tuples.
        For each iteration, returns the latest eval run for each eval name.
        """
        EvalQuery = Query()
        documents = self.table.search(EvalQuery.optimise_run_id == str(optimise_run_id))

        if not documents:
            return []

        # Group by iteration and eval name, keeping only the latest
        iteration_map: dict[int, dict[str, tuple[str, dict]]] = {}

        for doc in documents:
            iteration = doc['iteration_number']
            eval_name = doc['eval_name']
            timestamp = doc['timestamp']

            if iteration not in iteration_map:
                iteration_map[iteration] = {}

            # Keep only the latest timestamp for each eval name
            if eval_name not in iteration_map[iteration] or timestamp > iteration_map[iteration][eval_name][0]:
                iteration_map[iteration][eval_name] = (timestamp, doc['result'])

        # Convert to list of tuples
        result_tuples = []
        for iteration, eval_results in sorted(iteration_map.items()):
            results = [
                self._reconstruct_eval_result(result_dict)
                for _, result_dict in eval_results.values()
            ]
            result_tuples.append((iteration, results))

        return result_tuples

    async def get_iteration_results(self, optimise_run_id: UUID, iteration_number: int) -> list[EvalResult] | None:
        """Retrieve results for a specific iteration.

        Returns the latest eval run for each eval name in the iteration.
        Returns None if no results found.
        """
        EvalQuery = Query()
        documents = self.table.search(
            (EvalQuery.optimise_run_id == str(optimise_run_id)) &
            (EvalQuery.iteration_number == iteration_number)
        )

        if not documents:
            return None

        # Group by eval name, keeping only the latest
        latest_results: dict[str, tuple[str, dict]] = {}

        for doc in documents:
            eval_name = doc['eval_name']
            timestamp = doc['timestamp']

            # Keep only the latest timestamp for each eval name
            if eval_name not in latest_results or timestamp > latest_results[eval_name][0]:
                latest_results[eval_name] = (timestamp, doc['result'])

        return [
            self._reconstruct_eval_result(result_dict)
            for _, result_dict in latest_results.values()
        ]

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()

    def clear_run(self, optimise_run_id: UUID) -> None:
        """Delete all results for a specific optimisation run."""
        EvalQuery = Query()
        self.table.remove(EvalQuery.optimise_run_id == str(optimise_run_id))

    def clear_all(self) -> None:
        """Delete all stored results."""
        self.table.truncate()

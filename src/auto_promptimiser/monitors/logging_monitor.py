import logging
from uuid import UUID

from auto_promptimiser.core.base_monitor import BaseMonitor, IterationMetrics

logger = logging.getLogger(__name__)


class LoggingMonitor(BaseMonitor):
    """Simple monitor that logs progress using Python's logging module."""

    def __init__(self):
        self.best_accuracy = 0.0
        self.best_iteration = 0

    def on_optimization_start(self, run_id: UUID) -> None:
        logger.info(f"🚀 Starting optimization run: {run_id}")

    def on_iteration_start(self, run_id: UUID, iteration_number: int) -> None:
        logger.info(f"📝 Starting iteration {iteration_number}")

    def on_iteration_complete(self, metrics: IterationMetrics) -> None:
        if metrics.accuracy > self.best_accuracy:
            self.best_accuracy = metrics.accuracy
            self.best_iteration = metrics.iteration_number
            improvement_marker = " 🎯 NEW BEST!"
        else:
            improvement_marker = ""

        if metrics.iteration_number == 0:
            logger.info(
                f"✅ Initial evaluation complete - "
                f"Accuracy: {metrics.accuracy:.1f}% "
                f"({metrics.num_correct}/{metrics.total_evals} passed)"
            )
        else:
            logger.info(
                f"✅ Iteration {metrics.iteration_number} complete - "
                f"Accuracy: {metrics.accuracy:.1f}% "
                f"({metrics.num_correct}/{metrics.total_evals} passed) "
                f"| Best: {self.best_accuracy:.1f}% (iter {self.best_iteration})"
                f"{improvement_marker}"
            )

            if metrics.changelog:
                logger.info(f"   Changes: {metrics.changelog}")

    def on_optimization_complete(self, run_id: UUID, final_iteration: int) -> None:
        logger.info(
            f"🏁 Optimization complete! "
            f"Final iteration: {final_iteration} | "
            f"Best accuracy: {self.best_accuracy:.1f}% (iteration {self.best_iteration})"
        )

    def on_error(self, run_id: UUID, iteration_number: int, error: Exception) -> None:
        logger.error(
            f"❌ Error in iteration {iteration_number}: {str(error)}",
            exc_info=True
        )

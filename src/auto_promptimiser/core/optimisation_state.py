"""State management for optimization iterations."""

from dataclasses import dataclass, field
from auto_promptimiser.core.eval_entities import IterationHistoryEntry, IterationSnapshot, EvalSuiteResult
from auto_promptimiser.core.project_breakdown import ProjectBreakdown


MAX_SNAPSHOTS = 5


@dataclass
class OptimisationState:
    """Represents the current state of the optimization process."""
    iteration_history: list[IterationHistoryEntry]
    initial_eval_result: EvalSuiteResult | None
    project_breakdown: ProjectBreakdown
    iteration_snapshots: list[IterationSnapshot] = field(default_factory=list)
    # Tracks pending reset info to be applied to the next iteration's history entry
    pending_reset_from: int | None = None
    pending_reset_reason: str | None = None

    def to_str(self) -> str:
        """Build the comprehensive state message that appears at the start of each iteration."""
        message = "# Optimization State\n\n"

        # Section 1: History
        if self.iteration_history:
            message += "## Optimization History\n\n"

            # Show initial state from iteration 0
            if self.initial_eval_result:
                message += "### Initial State (Before Iteration 0)\n"
                summary = self.initial_eval_result.summarise()
                for result in self.initial_eval_result.results:
                    status = "PASS" if result.is_correct else "FAIL"
                    score_display = f"{result.score * 100:.1f}%"
                    message += f"- {result.eval_name}: {status} (Score: {score_display})\n"
                message += f"**Total**: {summary.accuracy:.1f}% ({summary.num_correct}/{summary.total} passed)\n\n"

            # Show all iteration results
            for entry in self.iteration_history:
                message += entry.to_str()
        else:
            # First iteration - show initial eval results
            message += "## Initial State\n\n"
            if self.initial_eval_result:
                message += "This is the first iteration. Initial evaluation results:\n"
                summary = self.initial_eval_result.summarise()
                for result in self.initial_eval_result.results:
                    status = "PASS" if result.is_correct else "FAIL"
                    score_display = f"{result.score * 100:.1f}%"
                    message += f"- {result.eval_name}: {status} (Score: {score_display})\n"
                message += f"**Total**: {summary.accuracy:.1f}% ({summary.num_correct}/{summary.total} passed)\n"
                message += "\n"

        # Section 2: Regression Warning (if applicable)
        regression_info = self._check_for_regression()
        if regression_info:
            message += "## ⚠️ Regression Detected\n\n"
            message += f"Pass rate dropped from {regression_info['baseline']:.1f}% to {regression_info['current']:.1f}% "
            message += f"(iteration {regression_info['regression_iter']}).\n"
            message += f"Best recorded state: iteration {regression_info['best_iter']} ({regression_info['best']:.1f}%)\n\n"
            message += "**Consider using `reset_to_iteration` to revert to a better state before making more changes.**\n\n"

        # Section 3: Known Limitations (if any)
        if self.project_breakdown.known_limitations:
            message += "## Known Limitations\n\n"
            message += "The following evals have been marked as not worth pursuing further:\n"
            for eval_name, limitation in self.project_breakdown.known_limitations.items():
                message += f"- **{eval_name}**: {limitation.reason}\n"
            message += "\n**Do not spend time trying to fix these evals.**\n\n"

        # Section 4: Project Breakdown
        message += "## Current Project Breakdown\n\n"
        message += self.project_breakdown.to_str()
        message += "\n"

        # Section 5: Instructions
        message += "## Instructions\n\n"
        message += "Continue optimizing the system to improve evaluation results. "
        message += "When you have made changes and are ready to test them, use the "
        message += "`end_iteration` action to run evaluations and proceed to the next iteration.\n"

        return message

    def _check_for_regression(self) -> dict | None:
        """Check if the last iteration caused a regression compared to baseline or best state.

        Returns dict with regression info if detected, None otherwise.
        """
        if not self.iteration_history or not self.initial_eval_result:
            return None

        baseline_accuracy = self.initial_eval_result.summarise().accuracy
        last_entry = self.iteration_history[-1]
        current_accuracy = last_entry.evals_result.summarise().accuracy

        # Find best accuracy and which iteration achieved it
        best_accuracy = baseline_accuracy
        best_iter = 0  # 0 represents initial/baseline
        for entry in self.iteration_history:
            entry_accuracy = entry.evals_result.summarise().accuracy
            if entry_accuracy > best_accuracy:
                best_accuracy = entry_accuracy
                best_iter = entry.iteration_num

        # Regression threshold: current is >5% worse than best
        regression_threshold = 5.0
        if current_accuracy < best_accuracy - regression_threshold:
            return {
                "baseline": baseline_accuracy,
                "current": current_accuracy,
                "best": best_accuracy,
                "best_iter": best_iter,
                "regression_iter": last_entry.iteration_num,
            }

        return None

    def get_snapshot(self, iteration_number: int) -> IterationSnapshot | None:
        """Get the snapshot for a specific iteration number."""
        for snapshot in self.iteration_snapshots:
            if snapshot.iteration_num == iteration_number:
                return snapshot
        return None

    def add_snapshot(self, snapshot: IterationSnapshot) -> None:
        """Add a new iteration snapshot, keeping only the most recent MAX_SNAPSHOTS."""
        self.iteration_snapshots.append(snapshot)
        if len(self.iteration_snapshots) > MAX_SNAPSHOTS:
            self.iteration_snapshots.pop(0)

    def set_pending_reset(self, from_iteration: int, reason: str) -> None:
        """Set pending reset info to be recorded in the next iteration's history."""
        self.pending_reset_from = from_iteration
        self.pending_reset_reason = reason

    def consume_pending_reset(self) -> tuple[int | None, str | None]:
        """Get and clear pending reset info. Returns (from_iteration, reason)."""
        from_iter = self.pending_reset_from
        reason = self.pending_reset_reason
        self.pending_reset_from = None
        self.pending_reset_reason = None
        return from_iter, reason

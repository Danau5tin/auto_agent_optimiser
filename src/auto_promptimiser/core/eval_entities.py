from dataclasses import dataclass
from typing import TYPE_CHECKING
import yaml

if TYPE_CHECKING:
    from auto_promptimiser.core.project_breakdown import ProjectBreakdown


@dataclass
class IterationSnapshot:
    """Snapshot of file states and project breakdown at an iteration boundary."""
    iteration_num: int
    file_states: dict[str, str]  # path -> content
    project_breakdown: 'ProjectBreakdown'  # copy of project breakdown at this point


@dataclass
class IterationHistoryEntry:
    """Record of a single iteration."""
    iteration_num: int
    changelog: str
    evals_result: 'EvalSuiteResult'
    reset_from: int | None = None  # If set, this iteration started by resetting from iteration N
    reset_reason: str | None = None

    def to_str(self) -> str:
        """Format this iteration history entry as a string."""
        summary = self.evals_result.summarise()

        message = f"### Iteration {self.iteration_num}\n"

        # Show reset info if this iteration involved a reset
        if self.reset_from is not None:
            message += f"**Reset**: Rolled back to iteration {self.reset_from} state"
            if self.reset_reason:
                message += f" (reason: \"{self.reset_reason}\")"
            message += "\n"

        message += f"**Changes**: {self.changelog}\n\n"
        message += "**Results**:\n"

        # Format individual results
        for result in self.evals_result.results:
            status = "PASS" if result.is_correct else "FAIL"
            score_display = f"{result.score * 100:.1f}%"
            message += f"- {result.eval_name}: {status} (Score: {score_display})\n"

        # Add total
        message += f"**Total**: {summary.accuracy:.1f}% ({summary.num_correct}/{summary.total} passed)\n\n"

        return message

@dataclass
class EvalCallbackArgs:
    """
    The client can use this information to re-run evaluations and decide whether optimisation should continue.
    """
    iteration_count: int = 0
    evals_to_run: list[str] | None = None
    num_attempts: int = 1

@dataclass
class EvalAttempt:
    """Result of a single attempt of an evaluation."""
    attempt_number: int
    score: float
    payload: dict
    trajectory: list[dict]
    hidden_payload: dict | None = None
    is_correct: bool = False

    def to_yaml(self) -> str:
        return yaml.dump({
            "attempt_number": self.attempt_number,
            "score": self.score,
            "is_correct": self.is_correct,
            "payload": self.payload,
        })

@dataclass
class EvalResult:
    eval_name: str
    eval_desc: str
    attempts: list[EvalAttempt]
    threshold: float = 1.0  # Score threshold to be considered "correct"

    @property
    def is_correct(self) -> bool:
        """Derived property: eval is correct if ANY attempt passed."""
        return any(attempt.is_correct for attempt in self.attempts)

    @property
    def score(self) -> float:
        """Average score across attempts."""
        if not self.attempts:
            return 0.0
        return sum(attempt.score for attempt in self.attempts) / len(self.attempts)

    def to_yaml(self) -> str:
        return yaml.dump({
            "eval_name": self.eval_name,
            "eval_desc": self.eval_desc,
            "attempts": [yaml.safe_load(a.to_yaml()) for a in self.attempts],
            "is_correct": self.is_correct,
        })

class ResultsSummary:
    def __init__(self, num_correct: int, num_incorrect: int, average_score: float):
        self.num_correct = num_correct
        self.num_incorrect = num_incorrect
        self.average_score = average_score

    @property
    def total(self) -> int:
        return self.num_correct + self.num_incorrect

    @property
    def accuracy(self) -> float:
        """Percentage of evals that passed (score >= threshold)."""
        if self.total == 0:
            return 0.0
        return (self.num_correct / self.total) * 100.0

    @property
    def average_score_percentage(self) -> float:
        """Average score across all evals as percentage."""
        return self.average_score * 100.0

    def to_yaml(self) -> str:
        return yaml.dump({
            "total_evals": self.total,
            "num_correct": self.num_correct,
            "num_incorrect": self.num_incorrect,
            "accuracy": f"{self.accuracy:.2f}%",
            "average_score": f"{self.average_score_percentage:.2f}%",
        })


@dataclass
class EvalSuiteResult:
    result_str: str
    results: list[EvalResult]
    end_optimisation: bool = False

    def summarise(self) -> ResultsSummary:
        num_correct = 0
        num_incorrect = 0
        total_score = 0.0

        for result in self.results:
            if result.is_correct:
                num_correct += 1
            else:
                num_incorrect += 1
            total_score += result.score

        average_score = total_score / len(self.results) if self.results else 0.0
        return ResultsSummary(
            num_correct=num_correct,
            num_incorrect=num_incorrect,
            average_score=average_score
        )

    def to_yaml(self) -> str:
        summary = self.summarise()
        results_yaml = [result.to_yaml() for result in self.results]
        return yaml.dump({
            "summary": yaml.safe_load(summary.to_yaml()),
            "results": [yaml.safe_load(r) for r in results_yaml],
        })

    def to_formatted_string(self, iteration_number: int) -> str:
        summary = self.summarise()

        lines = [
            "# Eval Results",
            f"## Iteration: {iteration_number}",
            "",
            "### Summary",
            f"- Total: {summary.total}",
            f"- Correct: {summary.num_correct}/{summary.total} ({summary.accuracy:.2f}%)",
            "",
            "### Individual Results",
        ]

        for i, result in enumerate(self.results, start=1):
            num_attempts = len(result.attempts)
            passed_attempts = sum(1 for a in result.attempts if a.is_correct)
            
            status = "PASS" if result.is_correct else "FAIL"
            score_display = f"{result.score * 100:.1f}%"
            
            lines.append(f"{i}. {result.eval_name} - {status} ({passed_attempts}/{num_attempts} attempts passed)")
            lines.append(f"   Description: {result.eval_desc}")
            
            if num_attempts > 0:
                lines.append("   Attempts:")
                for attempt in result.attempts:
                    attempt_status = "PASS" if attempt.is_correct else "FAIL"
                    attempt_score = f"{attempt.score * 100:.1f}%"
                    lines.append(f"   - Attempt {attempt.attempt_number}: {attempt_status} (Score: {attempt_score})")
                    
                    if attempt.payload:
                        payload_str = yaml.dump(attempt.payload, default_flow_style=False, indent=2)
                        indented_payload = "\n".join(f"     {line}" for line in payload_str.strip().split("\n"))
                        lines.append(f"     Details:\n{indented_payload}")
            
            lines.append("")

        return "\n".join(lines)
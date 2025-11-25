"""Reusable TBench evaluation runner for scenario tests."""

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Coroutine, Any

from auto_promptimiser.core.eval_entities import (
    EvalCallbackArgs,
    EvalAttempt,
    EvalResult,
    EvalSuiteResult,
)
from auto_promptimiser.core.file_manager import BaseFileManager


@dataclass
class TBenchConfig:
    """Configuration for TBench evaluation runs."""

    coding_llm_model: str = "openrouter/z-ai/glm-4.6"
    coding_llm_api_key: str = ""
    n_concurrent: int = 8
    dataset: str = "terminal-bench@2.0"


class TBenchEvalRunner:
    """
    Handles running Harbor/TBench evaluations and parsing results.

    This class extracts the common logic for:
    - Copying workspace files to iteration directories
    - Validating agent imports
    - Running Harbor evaluations
    - Parsing CTRF results and trajectories
    """

    def __init__(
        self,
        temp_dir: Path,
        config: TBenchConfig | None = None,
        default_evals: list[str] | None = None,
    ):
        """
        Args:
            temp_dir: The temporary directory containing the agent code.
            config: TBench configuration. If None, uses defaults.
            default_evals: Default eval task names to run when "all" is requested.
                          If None, no --task-name args are passed (runs all tasks).
        """
        self.temp_dir = temp_dir
        self.config = config or TBenchConfig()
        self.default_evals = default_evals

    def copy_workspace_files(self, destination_dir: Path) -> None:
        """Copy all files from the temp workspace to a local directory."""
        for src_path in self.temp_dir.rglob("*"):
            if src_path.is_file():
                relative_path = src_path.relative_to(self.temp_dir)
                dest_path = destination_dir / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)

        # Create __init__.py to make it a Python package
        (destination_dir / "__init__.py").touch()

    def validate_agent_import(self, agent_import_path: str) -> str | None:
        """
        Validate the agent can be imported.

        Returns:
            Error message if validation failed, None if success.
        """
        module_path, class_name = agent_import_path.split(":")
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                f"from {module_path} import {class_name}; print('Success:', {class_name})",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_output = result.stderr or result.stdout
            return f"Agent import validation failed (Unable to run evals):\n{error_output}"

        return None

    def parse_single_attempt(
        self, attempt_dir: Path, attempt_num: int
    ) -> EvalAttempt | None:
        """Parse a single attempt from a Harbor result directory."""
        verifier_dir = attempt_dir / "verifier"
        if not verifier_dir.exists():
            return None

        ctrf_path = verifier_dir / "ctrf.json"
        reward_path = verifier_dir / "reward.txt"

        if not ctrf_path.exists() or not reward_path.exists():
            return None

        # Parse reward (score)
        try:
            score = float(reward_path.read_text().strip())
        except (ValueError, FileNotFoundError):
            score = 0.0

        # Parse ctrf.json
        try:
            with open(ctrf_path, "r") as f:
                ctrf_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

        tests = ctrf_data.get("results", {}).get("tests", [])

        # Extract test information
        test_details = []
        for test in tests:
            test_info = {
                "name": test.get("name", "unknown"),
                "status": test.get("status", "unknown"),
            }
            if "trace" in test:
                test_info["trace"] = test["trace"]
            if "message" in test:
                test_info["message"] = test["message"]
            test_details.append(test_info)

        # Determine if all tests passed
        is_correct = (
            all(test.get("status") == "passed" for test in tests) and score == 1.0
        )

        # Parse trajectory from agent/trajectory.json
        trajectory = []
        trajectory_path = attempt_dir / "agent" / "trajectory.json"
        if trajectory_path.exists():
            try:
                with open(trajectory_path, "r") as f:
                    trajectory_data = json.load(f)
                    trajectory = trajectory_data.get("steps", [])
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        return EvalAttempt(
            attempt_number=attempt_num,
            score=score,
            is_correct=is_correct,
            payload={
                "tests": test_details,
                "total_tests": len(tests),
                "passed_tests": sum(1 for t in tests if t.get("status") == "passed"),
            },
            trajectory=trajectory,
        )

    def _resolve_evals_to_run(self, evals_to_run: list[str] | None) -> list[str] | None:
        """
        Resolve which evals to run based on input and defaults.

        Args:
            evals_to_run: The evals requested by the callback args.

        Returns:
            List of eval names to pass as --task-name args, or None to run all.
        """
        if not evals_to_run:
            # No evals specified - use defaults (which may be None for "run all")
            return self.default_evals

        if evals_to_run == ["all"]:
            # Explicit "all" - use defaults
            return self.default_evals

        # Specific evals requested - use them directly
        return evals_to_run

    def _build_harbor_command(
        self, agent_import_path: str, num_attempts: int, task_names: list[str] | None
    ) -> list[str]:
        """Build the harbor CLI command."""
        cmd = [
            "harbor",
            "run",
            "--dataset",
            self.config.dataset,
            "--agent-import-path",
            agent_import_path,
            "--n-concurrent",
            str(self.config.n_concurrent),
            "--n-attempts",
            str(num_attempts),
        ]

        if task_names and len(task_names) > 0:
            for task_name in task_names:
                cmd.extend(["--task-name", task_name])

        return cmd

    def _parse_job_results(self, latest_job_dir: Path) -> list[EvalResult]:
        """Parse results from a Harbor job directory."""
        # Group attempt directories by task name (e.g., "fix-git__abc" -> "fix-git")
        task_attempts: dict[str, list[Path]] = {}
        for attempt_dir in latest_job_dir.iterdir():
            if not attempt_dir.is_dir() or "__" not in attempt_dir.name:
                continue

            # Extract task name (part before __)
            task_name = attempt_dir.name.split("__")[0]
            if task_name not in task_attempts:
                task_attempts[task_name] = []
            task_attempts[task_name].append(attempt_dir)

        # Parse results for each task
        eval_results = []
        for task_name, attempt_dirs in task_attempts.items():
            attempts = []
            for attempt_num, attempt_dir in enumerate(attempt_dirs, start=1):
                attempt = self.parse_single_attempt(attempt_dir, attempt_num)
                if attempt:
                    attempts.append(attempt)

            if attempts:
                eval_results.append(
                    EvalResult(
                        eval_name=task_name,
                        eval_desc=f"Harbor eval: {task_name}",
                        attempts=attempts,
                    )
                )

        return eval_results

    def create_eval_callback(
        self, file_manager: BaseFileManager
    ) -> Callable[[EvalCallbackArgs], Coroutine[Any, Any, EvalSuiteResult]]:
        """
        Create the evaluation callback for the optimiser agent.

        Args:
            file_manager: File manager (unused but required for callback signature).

        Returns:
            Async callback function for running evaluations.
        """

        async def callback(args: EvalCallbackArgs) -> EvalSuiteResult:
            # Create a directory for this iteration's evaluation
            eval_runs_dir = Path("./eval_runs")
            eval_runs_dir.mkdir(parents=True, exist_ok=True)
            (eval_runs_dir / "__init__.py").touch()

            iteration_dir = eval_runs_dir / f"iter_{args.iteration_count}"
            iteration_dir.mkdir(parents=True, exist_ok=True)

            # Copy all files from temp workspace to iteration directory
            self.copy_workspace_files(iteration_dir)

            # Build agent import path
            agent_import_path = (
                f"eval_runs.iter_{args.iteration_count}.agent:CodingAgent"
            )

            # Validate the agent can be imported before running Harbor
            validation_error = self.validate_agent_import(agent_import_path)
            if validation_error:
                return EvalSuiteResult(
                    result_str=validation_error,
                    results=[],
                    end_optimisation=False,
                )

            # Set up environment
            env = os.environ.copy()
            env["CODING_LLM_MODEL"] = self.config.coding_llm_model
            env["CODING_LLM_API_KEY"] = self.config.coding_llm_api_key

            # Resolve which evals to run
            task_names = self._resolve_evals_to_run(args.evals_to_run)

            # Build and run command
            cmd = self._build_harbor_command(
                agent_import_path, args.num_attempts, task_names
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)

            if result.returncode != 0:
                return EvalSuiteResult(
                    result_str=f"Harbor run failed with error:\n{result.stderr}\n{result.stdout}. If this is consistent, finish the optimisation.",
                    results=[],
                    end_optimisation=False,
                )

            # Find the most recent jobs directory
            jobs_dir = Path("./jobs")
            if not jobs_dir.exists():
                return EvalSuiteResult(
                    result_str="Jobs directory not found after Harbor run",
                    results=[],
                    end_optimisation=False,
                )

            # Get most recent timestamped directory
            job_dirs = sorted(
                [d for d in jobs_dir.iterdir() if d.is_dir()], key=lambda d: d.name
            )
            if not job_dirs:
                return EvalSuiteResult(
                    result_str="No job directories found",
                    results=[],
                    end_optimisation=False,
                )

            latest_job_dir = job_dirs[-1]
            eval_results = self._parse_job_results(latest_job_dir)

            # Determine if all evals passed
            all_passed = all(result.is_correct for result in eval_results)

            return EvalSuiteResult(
                result_str=f"Completed {len(eval_results)} Harbor evaluations.",
                results=eval_results,
                end_optimisation=all_passed,
            )

        return callback

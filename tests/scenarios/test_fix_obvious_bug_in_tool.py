"""Test scenario: Agent can fix an obvious bug in tool code."""

from typing import List

from auto_promptimiser.core.eval_entities import (
    EvalCallbackArgs,
    EvalAttempt,
    EvalResult,
    EvalSuiteResult,
)
from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from tests.mocks.in_memory_file_manager import InMemoryFileManager
from tests.mocks.scripted_bash_executor import ScriptedBashExecutor
from tests.scenarios.assets.load_asset import load_asset
from tests.scenarios.base_scenario import BaseScenario


class TestFixObviousBug(BaseScenario):
    """
    Scenario: Agent identifies and fixes an obvious bug in calculator tool.

    Setup: Calculator's add operation incorrectly multiplies result by 9.
    Goal: Agent should read the code, identify the bug, and fix it.
    Success: Addition returns correct result (e.g., 5 + 7 = 12, not 108).
    """

    def create_traj(self, calculator_resp: str) -> List[dict]:
        return [
            {
                "role": "user",
                "content": "What is 5 + 7?",
            },
            {
                "role": "assistant",
                "content": '<calculator>\nfloat_a = 5\nfloat_b = 7\noperation = "add"</calculator>',
            },
            {"role": "user", "content": calculator_resp},
            {"role": "assistant", "content": "The answer is 108."},
        ]

    @property
    def asset_dir(self) -> str:
        return "calculator_agent"

    def create_file_manager(self) -> BaseFileManager:
        return InMemoryFileManager(
            initial_files={
                "calculator_tool.py": load_asset(
                    f"{self.asset_dir}/calculator_tool_broken.py"
                ),
                "agent.py": load_asset(f"{self.asset_dir}/agent.py"),
                "project_breakdown.yaml": self.project_breakdown.to_str(),
            }
        )

    def create_bash_executor(self) -> BaseBashExecutor:
        return ScriptedBashExecutor()

    async def verify_success(self, file_manager: BaseFileManager) -> None:
        content, is_error = await file_manager.read_file("calculator_tool.py")
        assert not is_error, "calculator_tool.py should exist"

        assert "* 9" not in content, "Bug multiplication by 9 should be removed"

        assert "return a + b" in content or "return (a + b)" in content, (
            "Addition should return a + b without extra multiplication"
        )

    def oracle_responses(self) -> list[str]:
        return [
            # Turn 1: Analyze failing eval, decide to read the code
            """I see that the basic_addition_test is failing. The agent is returning 108 instead of 12 for "5 + 7".
This suggests there's a bug in the calculator tool. Let me examine the calculator implementation.

{"action_type": "read", "file_path": "calculator_tool.py"}
""",
            # Turn 2: Found the bug, apply fix
            """I found the bug! In the calculate function, when performing addition, b is being multiplied by 9 due to operator precedence:
`return a + b * 9`

This is why 5 + 7 becomes 5 + (7 * 9) = 5 + 63 = 68. Let me fix this.

{"action_type": "edit", "file_path": "calculator_tool.py", "old_string": "        return a + b * 9", "new_string": "        return a + b"}
""",
            # Turn 3: Run evals to verify fix
            """I've fixed the bug. Now let me run the evaluation suite to verify the fix works.

{"action_type": "run_eval_suite", "evals_to_run": ["all"]}
""",
            # Turn 4: Success, finish
            """Excellent! The evaluation passed. The addition test now correctly returns 12 for "5 + 7".
The bug has been fixed successfully.

{"action_type": "finish", "message": "Successfully fixed the multiplication bug in the calculator tool. All evaluations now pass."}
""",
        ]

    def oracle_eval_callback(self):
        call_count = 0

        def create_payload(calculator_resp: str) -> dict:
            return {
                "question": "What is 5 + 7?",
                "expected_answer": "12",
                "final_response": f"The answer is ${calculator_resp}.",
            }

        async def callback(args: EvalCallbackArgs) -> EvalSuiteResult:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return EvalSuiteResult(
                    result_str="Completed 1 evals.",
                    results=[
                        EvalResult(
                            eval_name="basic_addition_test",
                            eval_desc="Test if agent can perform basic addition",
                            attempts=[
                                EvalAttempt(
                                    attempt_number=1,
                                    score=0.0,
                                    is_correct=False,
                                    payload=create_payload("108"),
                                    trajectory=self.create_traj(calculator_resp="108"),
                                )
                            ],
                        )
                    ],
                    end_optimisation=False,
                )
            else:
                return EvalSuiteResult(
                    result_str="Completed 1 evals.",
                    results=[
                        EvalResult(
                            eval_name="basic_addition_test",
                            eval_desc="Test if agent can perform basic addition",
                            attempts=[
                                EvalAttempt(
                                    attempt_number=1,
                                    score=1.0,
                                    is_correct=True,
                                    payload=create_payload("12"),
                                    trajectory=self.create_traj(calculator_resp="12"),
                                )
                            ],
                        )
                    ],
                    end_optimisation=True,
                )

        return callback

    def real_eval_callback(self, file_manager: BaseFileManager):
        async def callback(args: EvalCallbackArgs) -> EvalSuiteResult:
            # Use get_file_content for raw code (without line numbers) for exec()
            code = await file_manager.get_file_content("calculator_tool.py")
            if code is None:
                raise ValueError("Failed to read calculator_tool.py: file not found")

            local_vars = {}
            exec(code, local_vars)
            calculate = local_vars["calculate"]

            try:
                result = calculate(5, 7, "add")
                is_correct = result == 12
            except Exception as e:
                result = f"Error: {e}"
                is_correct = False

            return EvalSuiteResult(
                result_str="Completed 1 evals.",
                results=[
                    EvalResult(
                        eval_name="basic_addition_test",
                        eval_desc="Test if agent can perform basic addition",
                        attempts=[
                            EvalAttempt(
                                attempt_number=1,
                                score=1.0 if is_correct else 0.0,
                                is_correct=is_correct,
                                payload={
                                    "question": "What is 5 + 7?",
                                    "expected_answer": "12",
                                    "actual_result": str(result),
                                },
                                trajectory=self.create_traj(str(result)),
                            )
                        ],
                    )
                ],
                end_optimisation=is_correct,
            )

        return callback


async def main():
    scenario = TestFixObviousBug()
    await scenario.test_real_llm()


if __name__ == "__main__":
    # Setup logging
    import logging
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(main())

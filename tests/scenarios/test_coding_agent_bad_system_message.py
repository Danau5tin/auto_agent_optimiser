"""
Test scenario: Agent can fix flawed reasoning in a system message.

The target coding agent has a system message with completely broken logic:
it instructs the agent to call "finish" FIRST before doing any work.
This causes immediate task termination without any actual work being done.

The optimiser agent should identify this obviously wrong instruction and
fix the system message so finish is called at the END of tasks, not the start.
"""

import os
import shutil
import tempfile
from pathlib import Path

from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from auto_promptimiser.agent.local_tools.local_file_manager import LocalFileManager
from auto_promptimiser.agent.local_tools.local_bash_executor import LocalBashExecutor
from tests.scenarios.assets.load_asset import load_asset
from tests.scenarios.base_scenario import BaseScenario
from tests.scenarios.tbench_eval_runner import TBenchEvalRunner, TBenchConfig


class TestCodingAgentBadSystemMessage(BaseScenario):
    """
    Scenario where a coding agent has a flawed system message that instructs
    it to call "finish" FIRST before doing any work, causing immediate termination.

    The optimiser should identify and fix this obviously broken logic.
    """

    def __init__(self):
        super().__init__()
        self.temp_dir: Path | None = None
        self._tbench_runner: TBenchEvalRunner | None = None

    @property
    def asset_dir(self) -> str:
        return "coding_agent_with_bad_system_message"

    @property
    def default_evals(self) -> list[str] | None:
        """Default evals to run when 'all' is requested."""
        return ["fix-git"]

    @property
    def tbench_config(self) -> TBenchConfig:
        """TBench configuration."""
        return TBenchConfig(
            coding_llm_model=os.getenv("TARGET_LLM_MODEL", "openrouter/qwen/qwen3-30b-a3b"),
            coding_llm_api_key=os.getenv("TARGET_LLM_API_KEY"),
        )

    async def setup(self) -> None:
        """Set up a temporary directory with initial files."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="coding_agent_bad_sys_msg_"))

        initial_files = {
            "agent.py": load_asset(f"{self.asset_dir}/agent.py"),
            "tool_call_entities.py": load_asset(f"{self.asset_dir}/tool_call_entities.py"),
            "file_system_tool_handler.py": load_asset(f"{self.asset_dir}/file_system_tool_handler.py"),
            "project_breakdown.yaml": self.project_breakdown.to_str(),
        }

        for file_path, content in initial_files.items():
            full_path = self.temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Initialize the TBench runner
        self._tbench_runner = TBenchEvalRunner(
            temp_dir=self.temp_dir,
            config=self.tbench_config,
            default_evals=self.default_evals,
        )

    async def teardown(self) -> None:
        """Clean up the temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_file_manager(self) -> BaseFileManager:
        """Create file manager for the temp directory."""
        if not self.temp_dir:
            raise RuntimeError("Temp directory not initialized. Call setup() first.")

        return LocalFileManager(root_dir=self.temp_dir)

    def create_bash_executor(self) -> BaseBashExecutor:
        """Create bash executor for the temp directory."""
        if not self.temp_dir:
            raise RuntimeError("Temp directory not initialized. Call setup() first.")

        return LocalBashExecutor(root_dir=self.temp_dir)

    async def verify_success(self, file_manager: BaseFileManager) -> None:
        """Verify that the system message has been fixed."""
        agent_content, is_error = await file_manager.read_file("agent.py")
        if is_error:
            raise AssertionError(f"Failed to read agent.py: {agent_content}")

        # Check that the bad "call finish first" advice has been removed
        bad_advice_indicators = [
            "call the finish action as your first action",
            "finish action as your first",
            "must be called first",
            "always call finish first",
            "call finish first before any other",
        ]

        for indicator in bad_advice_indicators:
            if indicator.lower() in agent_content.lower():
                raise AssertionError(
                    f"Verification failed: System message still contains bad advice: '{indicator}'"
                )

        # Check that finish is still documented (just not as "call first")
        if "finish" not in agent_content.lower():
            raise AssertionError(
                "Verification failed: finish action should still be documented in the system message"
            )

    def real_eval_callback(self, file_manager: BaseFileManager):
        if not self._tbench_runner:
            raise RuntimeError("TBench runner not initialized. Call setup() first.")
        return self._tbench_runner.create_eval_callback(file_manager)


async def main():
    scenario = TestCodingAgentBadSystemMessage()
    await scenario.test_real_llm()


if __name__ == "__main__":
    import logging
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)

    asyncio.run(main())

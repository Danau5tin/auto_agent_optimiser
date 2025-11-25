"""Base class for agent optimization scenario tests."""

from abc import ABC, abstractmethod
import os
from typing import Callable, Coroutine, Any
import pytest

from pathlib import Path

from auto_promptimiser.agent.optimiser_agent import OptimiserAgent
from auto_promptimiser.core.eval_entities import EvalCallbackArgs, EvalSuiteResult
from auto_promptimiser.core.project_breakdown import ProjectBreakdown, load_project_breakdown
from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from auto_promptimiser.core.base_monitor import BaseMonitor
from auto_promptimiser.monitors.logging_monitor import LoggingMonitor
from tests.mocks.scripted_llm_client import ScriptedLLMClient
from tests.mocks.in_memory_storage import InMemoryEvalStorage, InMemoryMessageStorage


class BaseScenario(ABC):
    """Base class for agent optimization scenarios."""

    @property
    @abstractmethod
    def asset_dir(self) -> str:
        """Directory name under tests/scenarios/assets/"""
        pass

    @property
    def project_breakdown(self) -> ProjectBreakdown:
        assets_dir = Path(__file__).parent / "assets"
        breakdown_path = assets_dir / f"{self.asset_dir}/project_breakdown.yaml"
        return load_project_breakdown(breakdown_path)

    @abstractmethod
    async def verify_success(self, file_manager: BaseFileManager) -> None:
        """Assert that the scenario goal was achieved."""
        pass

    def oracle_responses(self) -> list[str]:
        """Scripted LLM responses for oracle test. Override to enable oracle test."""
        raise NotImplementedError("Override oracle_responses to enable oracle test")

    def oracle_eval_callback(
        self,
    ) -> Callable[[EvalCallbackArgs], Coroutine[Any, Any, EvalSuiteResult]]:
        """Eval callback for oracle test. Override to enable oracle test."""
        raise NotImplementedError("Override oracle_eval_callback to enable oracle test")

    @abstractmethod
    def real_eval_callback(
        self, file_manager: BaseFileManager
    ) -> Callable[[EvalCallbackArgs], Coroutine[Any, Any, EvalSuiteResult]]:
        """Eval callback for real LLM test."""
        pass

    @abstractmethod
    def create_file_manager(self) -> BaseFileManager:
        """Create file manager for this scenario."""
        pass

    @abstractmethod
    def create_bash_executor(self) -> BaseBashExecutor:
        """Create bash executor for this scenario."""
        pass

    async def setup(self) -> None:
        """Optional setup hook called before test execution."""
        pass

    async def teardown(self) -> None:
        """Optional teardown hook called after test execution."""
        pass

    def create_agent(
        self,
        file_manager: BaseFileManager,
        bash_executor: BaseBashExecutor,
        eval_callback,
        model: str = "test-model",
        api_key: str = "test-key",
        monitor: BaseMonitor | None = None,
    ) -> OptimiserAgent:
        return OptimiserAgent(
            eval_storage=InMemoryEvalStorage(),
            message_storage=InMemoryMessageStorage(),
            file_manager=file_manager,
            bash_executor=bash_executor,
            eval_callback=eval_callback,
            project_breakdown=self.project_breakdown,
            monitor=monitor,
            model=model,
            api_key=api_key,
        )

    @pytest.mark.asyncio
    @pytest.mark.oracle
    async def test_oracle(self, monkeypatch):
        try:
            responses = self.oracle_responses()
            eval_callback = self.oracle_eval_callback()
        except NotImplementedError:
            pytest.skip("Oracle test not implemented for this scenario")

        file_manager = self.create_file_manager()
        bash_executor = self.create_bash_executor()
        scripted_llm = ScriptedLLMClient(responses=responses)

        monkeypatch.setattr(
            "auto_promptimiser.core.base_agent.get_llm_response",
            scripted_llm.get_mock_function(),
        )

        agent = self.create_agent(
            file_manager=file_manager,
            bash_executor=bash_executor,
            eval_callback=eval_callback,
        )

        await agent.optimise()
        await self.verify_success(file_manager)

    @pytest.mark.asyncio
    @pytest.mark.real_llm
    async def test_real_llm(self):
        model = os.environ.get("LLM_MODEL")
        api_key = os.environ.get("LLM_API_KEY")

        if not model or not api_key:
            pytest.skip("LLM_MODEL and LLM_API_KEY required")

        try:
            # Run optional setup hook
            await self.setup()

            file_manager = self.create_file_manager()
            bash_executor = self.create_bash_executor()

            agent = self.create_agent(
                file_manager=file_manager,
                bash_executor=bash_executor,
                eval_callback=self.real_eval_callback(file_manager),
                monitor=LoggingMonitor(),
                model=model,
                api_key=api_key,
            )

            await agent.optimise()
            await self.verify_success(file_manager)
        finally:
            # Run optional teardown hook
            await self.teardown()

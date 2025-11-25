"""Tests for SubAgentHandlers trajectory analysis functionality."""

import os
from pathlib import Path
from uuid import uuid4
import pytest

from auto_promptimiser.agent.actions.subagent_actions import DispatchTrajAnalysisAgentAction
from auto_promptimiser.agent.handlers.registry import HandlerContext
from auto_promptimiser.agent.handlers.subagent_handlers import SubAgentHandlers
from auto_promptimiser.core.eval_entities import EvalResult, EvalAttempt
from auto_promptimiser.core.project_breakdown import ProjectBreakdown, load_project_breakdown
from auto_promptimiser.subagent.manager import SubAgentManager
from tests.mocks.in_memory_storage import InMemoryEvalStorage
from tests.mocks.scripted_llm_client import ScriptedLLMClient


def get_test_project_breakdown() -> ProjectBreakdown:
    """Load the calculator agent project breakdown from test assets."""
    assets_dir = Path(__file__).parent / "scenarios" / "assets" / "calculator_agent"
    return load_project_breakdown(assets_dir / "project_breakdown.yaml")


def create_sample_trajectory() -> list[dict]:
    """Create a sample agent trajectory for testing."""
    return [
        {
            "source": "user",
            "content": "Calculate 5 + 3"
        },
        {
            "source": "assistant",
            "content": "I'll calculate this. The answer is 9."
        }
    ]


def create_sample_eval_result(eval_name: str = "test_eval") -> EvalResult:
    """Create a sample eval result with a trajectory."""
    return EvalResult(
        eval_name=eval_name,
        eval_desc="Test calculation evaluation",
        attempts=[
            EvalAttempt(
                attempt_number=1,
                score=0.0,
                is_correct=False,
                payload={"expected": 8, "actual": 9},
                trajectory=create_sample_trajectory(),
            )
        ],
    )


def create_scripted_report_response(report_message: str) -> str:
    """Create a scripted LLM response that includes a ReportAction."""
    return f'''{{
  "action_type": "report",
  "message": "{report_message}"
}}'''


class TestSubAgentHandlersOracle:
    """Oracle tests for SubAgentHandlers using scripted LLM responses."""

    @pytest.mark.asyncio
    @pytest.mark.oracle
    async def test_dispatch_traj_analysis_returns_report(self, monkeypatch):
        """Test that the handler correctly dispatches and returns a report."""
        # Setup
        eval_storage = InMemoryEvalStorage()
        trajectory_id = uuid4()
        iteration_number = 1
        eval_name = "calc_test"

        # Store a test eval result
        eval_result = create_sample_eval_result(eval_name)
        await eval_storage.store_iteration_results(
            trajectory_id, iteration_number, [eval_result]
        )

        # Create handler
        handlers = SubAgentHandlers(
            eval_storage=eval_storage,
            model="test-model",
            api_key="test-key",
            project_breakdown=get_test_project_breakdown(),
            subagent_manager=SubAgentManager(),
        )

        # Mock LLM to return a report
        report_content = (
            "The agent made an error at turn 2 where it did not use the calculator tool"
        )
        scripted_llm = ScriptedLLMClient(
            responses=[create_scripted_report_response(report_content)]
        )
        monkeypatch.setattr(
            "auto_promptimiser.core.base_agent.get_llm_response",
            scripted_llm.get_mock_function(),
        )

        # Create action
        action = DispatchTrajAnalysisAgentAction(
            initial_message="This agent is a calculator agent. It has access to a single calculator tool which it should use for calculations, get the result, and advise the user what the result is. Analyze this failed calculation trajectory",
            iteration_number=iteration_number,
            eval_name=eval_name,
        )

        context = HandlerContext(trajectory_id=trajectory_id)

        # Execute
        result, is_error = await handlers.handle_dispatch_traj_analysis_agent(
            action, context
        )

        # Verify
        assert not is_error
        assert report_content in result
        assert "dispatch_traj_analysis_agent" in result

    @pytest.mark.asyncio
    @pytest.mark.oracle
    async def test_dispatch_traj_analysis_handles_missing_iteration(self):
        """Test error handling when iteration doesn't exist."""
        eval_storage = InMemoryEvalStorage()
        trajectory_id = uuid4()

        handlers = SubAgentHandlers(
            eval_storage=eval_storage,
            model="test-model",
            api_key="test-key",
            project_breakdown=get_test_project_breakdown(),
            subagent_manager=SubAgentManager(),
        )

        action = DispatchTrajAnalysisAgentAction(
            initial_message="Analyze this",
            iteration_number=999,
            eval_name="nonexistent",
        )

        context = HandlerContext(trajectory_id=trajectory_id)

        result, is_error = await handlers.handle_dispatch_traj_analysis_agent(
            action, context
        )

        assert is_error
        assert "No evaluation results found" in result
        assert "999" in result

    @pytest.mark.asyncio
    @pytest.mark.oracle
    async def test_dispatch_traj_analysis_handles_missing_eval_name(self):
        """Test error handling when eval name doesn't exist."""
        eval_storage = InMemoryEvalStorage()
        trajectory_id = uuid4()
        iteration_number = 1

        # Store an eval with different name
        eval_result = create_sample_eval_result("other_eval")
        await eval_storage.store_iteration_results(
            trajectory_id, iteration_number, [eval_result]
        )

        handlers = SubAgentHandlers(
            eval_storage=eval_storage,
            model="test-model",
            api_key="test-key",
            project_breakdown=get_test_project_breakdown(),
            subagent_manager=SubAgentManager(),
        )

        action = DispatchTrajAnalysisAgentAction(
            initial_message="Analyze this",
            iteration_number=iteration_number,
            eval_name="nonexistent_eval",
        )

        context = HandlerContext(trajectory_id=trajectory_id)

        result, is_error = await handlers.handle_dispatch_traj_analysis_agent(
            action, context
        )

        assert is_error
        assert "No evaluation found with name" in result
        assert "nonexistent_eval" in result


class TestSubAgentHandlersRealLLM:
    """Real LLM tests for SubAgentHandlers."""

    @pytest.mark.asyncio
    @pytest.mark.real_llm
    async def test_real_llm_identifies_missing_tool_usage(self):
        """Test that LLM identifies when agent didn't use required tool."""
        model = os.environ.get("LLM_MODEL")
        api_key = os.environ.get("LLM_API_KEY")

        if not model or not api_key:
            pytest.skip("LLM_MODEL and LLM_API_KEY required")

        eval_storage = InMemoryEvalStorage()
        trajectory_id = uuid4()
        iteration_number = 1
        eval_name = "calc_tool_usage"

        # Trajectory where agent did mental math instead of using calculator tool
        failing_trajectory = [
            {
                "source": "user",
                "content": "What is 5 + 3?"
            },
            {
                "source": "assistant",
                "content": "I'll calculate this. The answer is 9."
            }
        ]

        eval_result = EvalResult(
            eval_name=eval_name,
            eval_desc="Calculator tool usage test",
            attempts=[
                EvalAttempt(
                    attempt_number=1,
                    score=0.0,
                    is_correct=False,
                    payload={
                        "expected": 8,
                        "actual": 9,
                    },
                    trajectory=failing_trajectory,
                )
            ],
        )

        await eval_storage.store_iteration_results(
            trajectory_id, iteration_number, [eval_result]
        )

        handlers = SubAgentHandlers(
            eval_storage=eval_storage,
            model=model,
            api_key=api_key,
            project_breakdown=get_test_project_breakdown(),
            subagent_manager=SubAgentManager(),
        )

        initial_msg = (
            "This agent is a calculator agent. It has access to a single "
            "calculator tool which it should use for calculations, get the "
            "result, and advise the user what the result is. "
            "Analyze this failed calculation trajectory."
        )

        action = DispatchTrajAnalysisAgentAction(
            initial_message=initial_msg,
            iteration_number=iteration_number,
            eval_name=eval_name,
        )

        context = HandlerContext(trajectory_id=trajectory_id)

        result, is_error = await handlers.handle_dispatch_traj_analysis_agent(
            action, context
        )

        # Verify
        assert not is_error, f"Expected success but got error: {result}"
        assert "dispatch_traj_analysis_agent" in result
        assert len(result) > 100, "Report should be substantive"

        # Report should identify that the tool was not used
        result_lower = result.lower()
        tool_keywords = ["tool", "calculator", "didn't use", "did not use", "failed to use"]
        assert any(kw in result_lower for kw in tool_keywords), (
            f"Report should identify missing tool usage. Got: {result}"
        )


async def main():
    scenario = TestSubAgentHandlersRealLLM()
    await scenario.test_real_llm_identifies_missing_tool_usage()

if __name__ == "__main__":
    # Setup logging
    import logging
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    asyncio.run(main())
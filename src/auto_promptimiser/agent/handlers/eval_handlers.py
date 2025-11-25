"""Handlers for eval-related actions."""

from typing import Callable, Awaitable, Tuple
import logging
from auto_promptimiser.agent.actions.eval_actions import RunEvalSuiteAction
from auto_promptimiser.agent.handlers.registry import HandlerContext
from auto_promptimiser.agent.handlers.utils import format_tool_output
from auto_promptimiser.core.eval_entities import EvalCallbackArgs, EvalSuiteResult
from auto_promptimiser.core.base_eval_storage import BaseEvalStorage

logger = logging.getLogger(__name__)


class EvalHandlers:
    """Handlers for eval-related actions.

    This class groups all eval operation handlers together since they
    share dependencies related to running evaluations.
    """

    def __init__(
        self,
        eval_callback: Callable[[EvalCallbackArgs], Awaitable[EvalSuiteResult]],
        eval_storage: BaseEvalStorage,
    ):
        self.eval_callback = eval_callback
        self.eval_storage = eval_storage

    async def run_evals(
        self,
        evals_to_run: list[str],
        iteration_count: int,
        run_id,
        iteration_number: int,
        num_attempts: int = 1,
        store: bool = True,
    ) -> EvalSuiteResult:
        """Run evaluations and store results. Returns the eval suite result."""
        eval_callback_args = EvalCallbackArgs(
            iteration_count=iteration_count,
            evals_to_run=evals_to_run,
            num_attempts=num_attempts,
        )

        eval_suite_result = await self.eval_callback(eval_callback_args)

        if store:
            await self.eval_storage.store_iteration_results(
                run_id=run_id,
                iteration_number=iteration_number,
                results=eval_suite_result.results,
            )

        return eval_suite_result

    async def handle_run_eval_suite(
        self, action: RunEvalSuiteAction, context: HandlerContext
    ) -> Tuple[str, bool]:
        try:
            eval_suite_result = await self.run_evals(
                evals_to_run=action.evals_to_run,
                iteration_count=context.iteration,
                run_id=context.trajectory_id,
                iteration_number=context.iteration,
                num_attempts=action.num_attempts,
            )

            # Format output
            summary_text = eval_suite_result.to_formatted_string(context.iteration)

            return format_tool_output("eval", summary_text), False
        except Exception as e:
            error_message = f"Error during eval suite execution: {str(e)}"
            return format_tool_output("eval", error_message), True

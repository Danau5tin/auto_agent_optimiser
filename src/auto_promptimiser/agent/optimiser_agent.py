import logging
import os
from typing import Awaitable, Callable
from uuid import uuid4

from auto_promptimiser.agent.actions.bash import BashAction
from auto_promptimiser.agent.actions.debug_log import DebugLogAction
from auto_promptimiser.agent.actions.file_actions import (
    EditAction,
    MultiEditAction,
    ReadAction,
    WriteAction,
)
from auto_promptimiser.agent.handlers.utils import format_tool_output
from auto_promptimiser.core.eval_entities import IterationHistoryEntry, IterationSnapshot
from auto_promptimiser.agent.actions.eval_actions import (
    RunEvalSuiteAction,
    EndIterationAction,
    UpdateProjectBreakdownAction,
    ProjectBreakdownUpdates,
    ResetToIterationAction,
)
from auto_promptimiser.agent.actions.finish import FinishAction
from auto_promptimiser.agent.actions.subagent_actions import (
    DispatchTrajAnalysisAgentAction,
    SendSubagentMessageAction,
)
from auto_promptimiser.agent.handlers import (
    HandlerRegistry,
    HandlerContext,
    FileHandlers,
    BashHandlers,
)
from auto_promptimiser.agent.handlers.eval_handlers import EvalHandlers
from auto_promptimiser.agent.handlers.subagent_handlers import SubAgentHandlers
from auto_promptimiser.subagent.manager import SubAgentManager
from auto_promptimiser.core.action import Action
from auto_promptimiser.core.base_agent import BaseAgent, ModelConfig
from auto_promptimiser.core.base_eval_storage import BaseEvalStorage
from auto_promptimiser.core.base_message_storage import BaseMessageStorage
from auto_promptimiser.core.base_parser import BaseParser
from auto_promptimiser.core.eval_entities import EvalCallbackArgs, EvalSuiteResult
from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from auto_promptimiser.core.base_optimiser_agent import BaseOptimiserAgent
from auto_promptimiser.core.project_breakdown import ProjectBreakdown
from auto_promptimiser.core.optimisation_state import OptimisationState
from auto_promptimiser.core.base_monitor import BaseMonitor, IterationMetrics
from auto_promptimiser.parsers.json_parser import JSONParser
from auto_promptimiser.agent.sys_msg import opt_agent_sys_msg_json

logger = logging.getLogger(__name__)


class OptimiserAgent(BaseAgent[Action, HandlerContext], BaseOptimiserAgent):
    def __init__(
        self,
        eval_storage: BaseEvalStorage,
        message_storage: BaseMessageStorage,
        file_manager: BaseFileManager,
        bash_executor: BaseBashExecutor,
        eval_callback: Callable[[EvalCallbackArgs], Awaitable[EvalSuiteResult]],
        project_breakdown: ProjectBreakdown,
        monitor: BaseMonitor | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(system_message=opt_agent_sys_msg_json)

        self.message_storage = message_storage
        self.file_manager = file_manager
        self.monitor = monitor
        self.model = model or os.getenv("LLM_MODEL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

        if not self.model or not self.api_key:
            raise ValueError("LLM_MODEL and LLM_API_KEY must be set via parameters or environment variables")

        self.state = OptimisationState(
            iteration_history=[],
            initial_eval_result=None,
            project_breakdown=project_breakdown,
        )

        # Create the subagent manager (disposed on end_iteration)
        self.subagent_manager = SubAgentManager()

        file_handlers = FileHandlers(file_manager)
        bash_handlers = BashHandlers(bash_executor)
        self.eval_handlers = EvalHandlers(
            eval_callback=eval_callback,
            eval_storage=eval_storage,
        )
        subagent_handlers = SubAgentHandlers(
            eval_storage=eval_storage,
            model=self.model,
            api_key=self.api_key,
            project_breakdown=self.state.project_breakdown,
            subagent_manager=self.subagent_manager,
        )

        self._setup_handler_registry(file_handlers, bash_handlers, self.eval_handlers, subagent_handlers)

    def _setup_handler_registry(self, file_handlers, bash_handlers, eval_handlers, subagent_handlers):
        self.handler_registry = HandlerRegistry()

        self.handler_registry.register(ReadAction, file_handlers.handle_read)
        self.handler_registry.register(WriteAction, file_handlers.handle_write)
        self.handler_registry.register(EditAction, file_handlers.handle_edit)
        self.handler_registry.register(MultiEditAction, file_handlers.handle_multi_edit)
        self.handler_registry.register(BashAction, bash_handlers.handle_bash)
        self.handler_registry.register(
            RunEvalSuiteAction, eval_handlers.handle_run_eval_suite
        )
        self.handler_registry.register(
            DispatchTrajAnalysisAgentAction,
            subagent_handlers.handle_dispatch_traj_analysis_agent
        )
        self.handler_registry.register(
            SendSubagentMessageAction,
            subagent_handlers.handle_send_subagent_message
        )

    def _setup_action_parser(self) -> BaseParser[Action]:
        return JSONParser[Action](
            mapping_tag_to_action_class={
                "bash": BashAction,
                "debug_log": DebugLogAction,
                "read": ReadAction,
                "write": WriteAction,
                "edit": EditAction,
                "multi_edit": MultiEditAction,
                "run_eval_suite": RunEvalSuiteAction,
                "end_iteration": EndIterationAction,
                "update_project_breakdown": UpdateProjectBreakdownAction,
                "dispatch_traj_analysis_agent": DispatchTrajAnalysisAgentAction,
                "send_subagent_message": SendSubagentMessageAction,
                "reset_to_iteration": ResetToIterationAction,
                "finish": FinishAction,
            }
        )

    def _get_model_config(self) -> ModelConfig:
        if not self.model or not self.api_key:
            raise ValueError("LLM_MODEL and LLM_API_KEY must be set before getting model config")
        return ModelConfig(model=self.model, api_key=self.api_key)

    async def _execute_action(
        self, action: Action, context: HandlerContext
    ) -> tuple[str, bool]:
        context.executed_actions.append(type(action))

        if isinstance(action, FinishAction):
            context.is_finished = True
            return "", False

        if isinstance(action, DebugLogAction):
            logger.info(f"[OptimiserAgent] {action.message}")
            return "", False

        if isinstance(action, EndIterationAction):
            return await self._handle_end_iteration(action, context)

        if isinstance(action, UpdateProjectBreakdownAction):
            return self._handle_update_project_breakdown(action)

        if isinstance(action, ResetToIterationAction):
            return await self._handle_reset_to_iteration(action, context)

        # RunEvalSuiteAction can't run alongside other actions (except DebugLogAction)
        if isinstance(action, RunEvalSuiteAction) and len(context.executed_actions) > 1:
            non_debug_actions = [a for a in context.executed_actions if a != DebugLogAction]
            if len(non_debug_actions) > 1:
                return (
                    "\nUnable to run eval suite alongside other actions in the same response.\n",
                    True,
                )

        # Dispose all subagents before running evals to ensure clean state
        if isinstance(action, RunEvalSuiteAction):
            disposed_count = self.subagent_manager.dispose_all()
            if disposed_count > 0:
                logger.info(f"Disposed {disposed_count} subagent(s) before running evals")

        formatted_response, is_error = await self.handler_registry.handle(
            action, context
        )
        return formatted_response, is_error

    async def _handle_end_iteration(
        self, action: EndIterationAction, context: HandlerContext
    ) -> tuple[str, bool]:
        try:
            eval_suite_result = await self.eval_handlers.run_evals(
                evals_to_run=["all"],
                iteration_count=context.iteration,
                run_id=context.trajectory_id,
                iteration_number=context.iteration,
            )

            self._apply_project_breakdown_updates(action.project_breakdown_updates)

            # Capture snapshot of current state for potential future reset
            await self._capture_snapshot(context.iteration + 1)

            # Dispose all active subagents at end of iteration
            disposed_count = self.subagent_manager.dispose_all()
            if disposed_count > 0:
                logger.info(f"Disposed {disposed_count} subagent(s) at end of iteration")

            # Check for pending reset info from earlier in this iteration
            reset_from, reset_reason = self.state.consume_pending_reset()

            context.should_collapse_context = True
            context.iteration_history_entry = IterationHistoryEntry(
                iteration_num=context.iteration,
                changelog=action.changelog_entry,
                evals_result=eval_suite_result,
                reset_from=reset_from,
                reset_reason=reset_reason,
            )

            # Notify monitor of iteration completion
            if self.monitor:
                metrics = IterationMetrics(
                    run_id=context.trajectory_id,
                    iteration_number=context.iteration,
                    changelog=action.changelog_entry,
                    eval_result=eval_suite_result,
                )
                self.monitor.on_iteration_complete(metrics)

            summary_text = eval_suite_result.to_formatted_string(context.iteration)
            return format_tool_output("end_iteration", summary_text), False

        except Exception as e:
            error_message = f"Error during end iteration: {str(e)}"
            logger.exception("Error in _handle_end_iteration")
            if self.monitor:
                self.monitor.on_error(context.trajectory_id, context.iteration, e)
            return format_tool_output("end_iteration", error_message), True

    def _handle_update_project_breakdown(
        self, action: UpdateProjectBreakdownAction
    ) -> tuple[str, bool]:
        """Update the project breakdown immediately without ending the iteration."""
        updated_items = self._apply_project_breakdown_updates(action.updates)

        if not updated_items:
            return format_tool_output(
                "update_project_breakdown",
                "No updates provided. Include 'files' and/or 'actions' in updates.",
            ), True

        summary = "Project breakdown updated:\n- " + "\n- ".join(updated_items)
        return format_tool_output("update_project_breakdown", summary), False

    async def _handle_reset_to_iteration(
        self, action: ResetToIterationAction, context: HandlerContext
    ) -> tuple[str, bool]:
        """Reset file states and project breakdown back to a previous iteration's snapshot."""
        target_iter = action.iteration_number

        # Validate iteration number
        snapshot = self.state.get_snapshot(target_iter)
        if snapshot is None:
            available = [s.iteration_num for s in self.state.iteration_snapshots]
            if available:
                msg = (
                    f"No snapshot found for iteration {target_iter}. "
                    f"Only the last 5 snapshots are retained. "
                    f"Available snapshots: {available}"
                )
            else:
                msg = f"No snapshot found for iteration {target_iter}. No snapshots available."
            return format_tool_output("reset_to_iteration", msg), True

        # Restore all files from the snapshot
        restored_files = []
        errors = []
        for file_path, content in snapshot.file_states.items():
            try:
                result, is_error = await self.file_manager.write_file(file_path, content)
                if is_error:
                    errors.append(f"{file_path}: {result}")
                else:
                    restored_files.append(file_path)
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")

        # Restore project breakdown state
        self.state.project_breakdown.restore_from(snapshot.project_breakdown)

        # Record the reset in state so it appears in next iteration's history
        self.state.set_pending_reset(target_iter, action.reason)

        # Build response
        response_parts = [f"Reset to iteration {target_iter} state."]
        if restored_files:
            response_parts.append(f"Restored {len(restored_files)} file(s): {', '.join(restored_files)}")
        response_parts.append("Restored project breakdown state.")
        if errors:
            response_parts.append(f"Errors: {'; '.join(errors)}")
        response_parts.append(f"Reason recorded: {action.reason}")

        logger.info(f"Reset to iteration {target_iter}: restored {len(restored_files)} files, project breakdown, {len(errors)} errors")

        return format_tool_output("reset_to_iteration", "\n".join(response_parts)), bool(errors)

    def _apply_project_breakdown_updates(
        self, updates: ProjectBreakdownUpdates
    ) -> list[str]:
        """Apply updates to the project breakdown and return list of updated items."""
        updated_items = []

        if updates.files:
            for filepath, description in updates.files.items():
                logger.info(f"Updating file in project breakdown: {filepath}")
                self.state.project_breakdown.update_file(filepath, description)
                updated_items.append(f"file: {filepath}")

        if updates.actions:
            for action_name, description in updates.actions.items():
                logger.info(f"Updating action in project breakdown: {action_name}")
                self.state.project_breakdown.update_action(action_name, description)
                updated_items.append(f"action: {action_name}")

        if updates.known_limitations:
            for eval_name, reason in updates.known_limitations.items():
                logger.info(f"Marking eval as known limitation: {eval_name}")
                self.state.project_breakdown.add_known_limitation(eval_name, reason)
                updated_items.append(f"known_limitation: {eval_name}")

        return updated_items

    async def optimise(self) -> None:
        run_id = uuid4()
        iter_num = 0

        # Notify monitor of optimization start
        if self.monitor:
            self.monitor.on_optimization_start(run_id)

        # Capture initial snapshot (iteration 0) before any changes
        await self._capture_snapshot(iter_num)

        # Run initial evals and capture results
        self.state.initial_eval_result = await self._exec_initial_evals(run_id, iter_num)

        # Notify monitor of initial eval completion
        if self.monitor:
            initial_metrics = IterationMetrics(
                run_id=run_id,
                iteration_number=0,
                changelog=None,
                eval_result=self.state.initial_eval_result,
            )
            self.monitor.on_iteration_complete(initial_metrics)

        # Build initial state message
        state_message = self.state.to_str()
        self.add_user_message(state_message)

        while True:
            context = HandlerContext(
                trajectory_id=run_id,
                iteration=iter_num,
            )


            should_terminate = await self.process_llm_turn(context)

            if should_terminate:
                logger.info("Optimisation completed successfully.")
                if self.monitor:
                    self.monitor.on_optimization_complete(run_id, iter_num)
                await self.message_storage.store_messages(run_id, self.message_history)
                break

            if context.should_collapse_context:
                if context.iteration_history_entry is None:
                    logger.error("Context collapse triggered but no iteration history entry found")
                    continue

                self.state.iteration_history.append(context.iteration_history_entry)

                self._collapse_context()
                iter_num += 1
                if self.monitor:
                    self.monitor.on_iteration_start(run_id, iter_num)

    def _collapse_context(self) -> None:
        """Reset message history with updated state."""
        system_msg = self.message_history[0]  # Preserve system message
        state_message = self.state.to_str()

        self.message_history = [
            system_msg,
            {"role": "user", "content": state_message}
        ]

        logger.info(f"Context collapsed. Message history reset to {len(self.message_history)} messages.")

    async def _post_eval_hooks(self, context: HandlerContext) -> None:
        """Extensible hooks that run after evals complete."""
        logger.info(f"Evals completed for iteration {context.iteration}")
        # TODO: Git commit
        # Future: Create git commit, send notifications, etc.

    async def _exec_initial_evals(self, run_id, iter_num) -> 'EvalSuiteResult':
        """Run initial evaluations and return results."""
        logger.info(f"Running initial evaluation suite for run {run_id}")

        return await self.eval_handlers.run_evals(
            evals_to_run=["all"],
            num_attempts=3,
            iteration_count=iter_num,
            run_id=run_id,
            iteration_number=iter_num,
        )

    async def _capture_snapshot(self, iteration_num: int) -> IterationSnapshot:
        """Capture the current state of all key files and project breakdown as a snapshot."""
        file_states: dict[str, str] = {}

        for file_path in self.state.project_breakdown.key_files.keys():
            try:
                content, is_error = await self.file_manager.read_file(file_path)
                if not is_error:
                    file_states[file_path] = content
                else:
                    logger.warning(f"Could not read file for snapshot: {file_path}")
            except Exception as e:
                logger.warning(f"Error reading file for snapshot {file_path}: {e}")

        snapshot = IterationSnapshot(
            iteration_num=iteration_num,
            file_states=file_states,
            project_breakdown=self.state.project_breakdown.copy(),
        )
        self.state.add_snapshot(snapshot)
        logger.info(f"Captured snapshot for iteration {iteration_num} with {len(file_states)} files")
        return snapshot

"""Handlers for bash-related actions."""

from typing import Tuple
from auto_promptimiser.agent.actions.bash import BashAction
from auto_promptimiser.core.trajectory_context import TrajectoryContext
from auto_promptimiser.core.bash_executor import BaseBashExecutor
from auto_promptimiser.agent.handlers.utils import format_tool_output


class BashHandlers:
    """Handlers for bash-related actions.

    This class groups all bash operation handlers together since they
    share the same dependency (bash_executor) and are conceptually related.
    """

    def __init__(self, bash_executor: BaseBashExecutor):
        self.bash_executor = bash_executor

    async def handle_bash(self, action: BashAction, context: TrajectoryContext) -> Tuple[str, bool]:
        output, is_error = await self.bash_executor.execute(
            action.cmd, action.block, action.timeout_secs
        )
        return format_tool_output("bash", output), is_error

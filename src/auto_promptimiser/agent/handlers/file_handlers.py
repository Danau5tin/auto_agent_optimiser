"""Handlers for file-related actions."""

from typing import Tuple
from auto_promptimiser.agent.actions.file_actions import (
    ReadAction,
    WriteAction,
    EditAction,
    MultiEditAction,
)
from auto_promptimiser.core.trajectory_context import TrajectoryContext
from auto_promptimiser.core.file_manager import BaseFileManager
from auto_promptimiser.agent.handlers.utils import format_tool_output


class FileHandlers:
    """Handlers for file-related actions.

    This class groups all file operation handlers together since they
    share the same dependency (file_manager) and are conceptually related.
    """

    def __init__(self, file_manager: BaseFileManager):
        self.file_manager = file_manager

    async def handle_read(
        self, action: ReadAction, context: TrajectoryContext
    ) -> Tuple[str, bool]:
        content, is_error = await self.file_manager.read_file(
            action.file_path, action.offset, action.limit
        )
        return format_tool_output(f"file_read_{action.file_path}", content), is_error

    async def handle_write(
        self, action: WriteAction, context: TrajectoryContext
    ) -> Tuple[str, bool]:
        content, is_error = await self.file_manager.write_file(
            action.file_path, action.content
        )
        return format_tool_output(f"file_write_{action.file_path}", content), is_error

    async def handle_edit(
        self, action: EditAction, context: TrajectoryContext
    ) -> Tuple[str, bool]:
        content, is_error = await self.file_manager.edit_file(
            action.file_path,
            action.old_string,
            action.new_string,
            action.replace_all,
        )
        return format_tool_output(f"file_edit_{action.file_path}", content), is_error

    async def handle_multi_edit(
        self, action: MultiEditAction, context: TrajectoryContext
    ) -> Tuple[str, bool]:
        # Convert Pydantic models to tuples for file_manager
        edits = [
            (edit.old_string, edit.new_string, edit.replace_all)
            for edit in action.edits
        ]
        content, is_error = await self.file_manager.multi_edit_file(
            action.file_path, edits
        )
        return format_tool_output("multi_edit", content), is_error

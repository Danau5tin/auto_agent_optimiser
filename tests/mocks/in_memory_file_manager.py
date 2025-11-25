"""In-memory file manager for testing."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from auto_promptimiser.core.file_manager import BaseFileManager


class InMemoryFileManager(BaseFileManager):
    """File manager that maintains filesystem state in memory.

    Useful for testing scenarios where you want to:
    - Set up initial file state
    - Verify file modifications without touching disk
    - Track all file operations performed
    """

    def __init__(self, initial_files: Optional[Dict[str, str]] = None, root_dir: Optional[Path] = None):
        super().__init__(root_dir=root_dir)
        self.files: Dict[str, str] = initial_files.copy() if initial_files else {}
        self.operation_log: List[Dict] = []

    def _resolve_path(self, file_path: str) -> str:
        """Resolve path relative to root_dir if set."""
        if self.root_dir and not Path(file_path).is_absolute():
            return str(self.root_dir / file_path)
        return file_path

    async def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, bool]:
        resolved_path = self._resolve_path(file_path)
        self.operation_log.append({
            "operation": "read",
            "file_path": resolved_path,
            "offset": offset,
            "limit": limit
        })

        if resolved_path not in self.files:
            return f"Error: File not found: {resolved_path}", True

        content = self.files[resolved_path]
        lines = content.splitlines(keepends=True)

        if offset is not None:
            lines = lines[offset - 1:]  # offset is 1-indexed
        if limit is not None:
            lines = lines[:limit]

        # Format with line numbers like the real implementation
        if offset is None:
            start_line = 1
        else:
            start_line = offset

        numbered_lines = []
        for i, line in enumerate(lines, start=start_line):
            numbered_lines.append(f"{i:6d}\t{line.rstrip()}")

        return "\n".join(numbered_lines), False

    async def write_file(self, file_path: str, content: str) -> Tuple[str, bool]:
        resolved_path = self._resolve_path(file_path)
        self.operation_log.append({
            "operation": "write",
            "file_path": resolved_path,
            "content": content
        })

        self.files[resolved_path] = content
        return f"Successfully wrote to {resolved_path}", False

    async def edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> Tuple[str, bool]:
        resolved_path = self._resolve_path(file_path)
        self.operation_log.append({
            "operation": "edit",
            "file_path": resolved_path,
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": replace_all
        })

        if resolved_path not in self.files:
            return f"Error: File not found: {resolved_path}", True

        content = self.files[resolved_path]

        if old_string not in content:
            return f"Error: String not found in file: {old_string[:50]}...", True

        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1

        self.files[resolved_path] = new_content
        return f"Successfully replaced {count} occurrence(s) in {resolved_path}", False

    async def multi_edit_file(
        self,
        file_path: str,
        edits: List[Tuple[str, str, bool]]
    ) -> Tuple[str, bool]:
        resolved_path = self._resolve_path(file_path)
        self.operation_log.append({
            "operation": "multi_edit",
            "file_path": resolved_path,
            "edits": edits
        })

        if resolved_path not in self.files:
            return f"Error: File not found: {resolved_path}", True

        content = self.files[resolved_path]
        for old_string, new_string, replace_all in edits:
            if old_string not in content:
                return f"Error: String not found in file: {old_string[:50]}...", True

            if replace_all:
                content = content.replace(old_string, new_string)
            else:
                content = content.replace(old_string, new_string, 1)

        self.files[resolved_path] = content
        return f"Successfully applied {len(edits)} edit(s) to {resolved_path}", False

    async def delete_file(self, file_path: str) -> Tuple[str, bool]:
        resolved_path = self._resolve_path(file_path)
        self.operation_log.append({
            "operation": "delete",
            "file_path": resolved_path
        })

        if resolved_path not in self.files:
            return f"Error: File not found: {resolved_path}", True

        del self.files[resolved_path]
        return f"Successfully deleted {resolved_path}", False

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get raw file content without formatting."""
        resolved_path = self._resolve_path(file_path)
        return self.files.get(resolved_path)

    def file_exists(self, file_path: str) -> bool:
        """Helper to check if file exists."""
        resolved_path = self._resolve_path(file_path)
        return resolved_path in self.files

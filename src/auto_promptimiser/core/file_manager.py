"""Abstract base class for file management operations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple


class BaseFileManager(ABC):
    """Abstract base class for managing file operations in different environments."""

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize file manager with optional root directory.

        Args:
            root_dir: Root directory for file operations. If provided, relative paths
                     will be resolved relative to this directory.
        """
        self.root_dir = root_dir

    @abstractmethod
    async def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, bool]:
        """Read file contents with optional offset and limit.

        Args:
            file_path: Path to the file to read
            offset: Optional line number to start reading from
            limit: Optional maximum number of lines to read

        Returns:
            Tuple of (content_or_error_message, is_error)
        """

    @abstractmethod
    async def write_file(self, file_path: str, content: str) -> Tuple[str, bool]:
        """Write content to a file.

        Args:
            file_path: Path to the file to write
            content: Content to write to the file

        Returns:
            Tuple of (success_or_error_message, is_error)
        """

    @abstractmethod
    async def edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> Tuple[str, bool]:
        """Edit file by replacing strings.

        Args:
            file_path: Path to the file to edit
            old_string: String to find and replace
            new_string: String to replace with
            replace_all: If True, replace all occurrences; if False, replace only first

        Returns:
            Tuple of (success_or_error_message, is_error)
        """

    @abstractmethod
    async def multi_edit_file(
        self,
        file_path: str,
        edits: List[Tuple[str, str, bool]]
    ) -> Tuple[str, bool]:
        """Perform multiple edits on a file.

        Args:
            file_path: Path to the file to edit
            edits: List of tuples (old_string, new_string, replace_all)

        Returns:
            Tuple of (success_or_error_message, is_error)
        """

    @abstractmethod
    async def delete_file(self, file_path: str) -> Tuple[str, bool]:
        """Delete a file.

        Args:
            file_path: Path to the file to delete

        Returns:
            Tuple of (success_or_error_message, is_error)
        """

    @abstractmethod
    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get raw file content without formatting (e.g., no line numbers).

        Args:
            file_path: Path to the file to read

        Returns:
            Raw file content as string, or None if file doesn't exist
        """
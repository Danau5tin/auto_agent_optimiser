"""Concrete implementation of file management operations for local filesystem."""

from pathlib import Path
from typing import List, Optional, Tuple

from auto_promptimiser.core.file_manager import BaseFileManager



class LocalFileManager(BaseFileManager):
    """File manager implementation for local filesystem operations."""

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path relative to root_dir if set.

        Args:
            file_path: Path to resolve (can be absolute or relative)

        Returns:
            Resolved Path object
        """
        path = Path(file_path)

        # If path is absolute, use it as-is
        if path.is_absolute():
            return path

        # If root_dir is set, resolve relative to it
        if self.root_dir is not None:
            return self.root_dir / path

        # Otherwise, use path as-is (will be relative to current working directory)
        return path

    async def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, bool]:
        """Read file contents with optional offset and limit.

        Args:
            file_path: Path to the file to read
            offset: Optional line number to start reading from (0-indexed)
            limit: Optional maximum number of lines to read

        Returns:
            Tuple of (content_or_error_message, is_error)
        """
        try:
            path = self._resolve_path(file_path)

            if not path.exists():
                return f"File not found: {file_path}", True

            if not path.is_file():
                return f"Path is not a file: {file_path}", True

            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Apply offset and limit if specified
            start = offset if offset is not None else 0
            end = start + limit if limit is not None else len(lines)

            selected_lines = lines[start:end]
            content = ''.join(selected_lines)

            return content, False

        except UnicodeDecodeError:
            return f"Unable to decode file as UTF-8: {file_path}", True
        except PermissionError:
            return f"Permission denied reading file: {file_path}", True
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}", True

    async def write_file(self, file_path: str, content: str) -> Tuple[str, bool]:
        """Write content to a file.

        Args:
            file_path: Path to the file to write
            content: Content to write to the file

        Returns:
            Tuple of (success_or_error_message, is_error)
        """
        try:
            path = self._resolve_path(file_path)

            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return f"Successfully wrote to file: {file_path}", False

        except PermissionError:
            return f"Permission denied writing to file: {file_path}", True
        except Exception as e:
            return f"Error writing to file {file_path}: {str(e)}", True

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
        try:
            path = self._resolve_path(file_path)

            if not path.exists():
                return f"File not found: {file_path}", True

            if not path.is_file():
                return f"Path is not a file: {file_path}", True

            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                # Debug logging to see the mismatch
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"String not found in {file_path}")
                logger.error(f"Looking for ({len(old_string)} chars):\n{repr(old_string)}")
                logger.error(f"File content ({len(content)} chars):\n{repr(content[:500])}")
                return f"String not found in file: {file_path}", True

            # If not replace_all, ensure string is unique
            if not replace_all:
                count = content.count(old_string)
                if count > 1:
                    return f"String appears {count} times in file. Use replace_all=True to replace all occurrences.", True

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            # Write back to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return f"Successfully replaced {count} occurrence(s) in {file_path}", False

        except UnicodeDecodeError:
            return f"Unable to decode file as UTF-8: {file_path}", True
        except PermissionError:
            return f"Permission denied editing file: {file_path}", True
        except Exception as e:
            return f"Error editing file {file_path}: {str(e)}", True

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
        try:
            path = self._resolve_path(file_path)

            if not path.exists():
                return f"File not found: {file_path}", True

            if not path.is_file():
                return f"Path is not a file: {file_path}", True

            if not edits:
                return "No edits provided", True

            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply each edit sequentially
            total_replacements = 0
            for i, (old_string, new_string, replace_all) in enumerate(edits, 1):
                # Check if old_string exists
                if old_string not in content:
                    # Debug logging to see the mismatch
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Edit {i}/{len(edits)} - String not found in {file_path}")
                    logger.error(f"Looking for ({len(old_string)} chars):\n{repr(old_string)}")
                    logger.error(f"Current content ({len(content)} chars):\n{repr(content[:500])}")
                    return (
                        f"Edit {i}/{len(edits)} failed: "
                        f"String not found in file: {file_path}",
                        True
                    )

                # If not replace_all, ensure string is unique
                if not replace_all:
                    count = content.count(old_string)
                    if count > 1:
                        return (
                            f"Edit {i}/{len(edits)} failed: "
                            f"String appears {count} times in file. "
                            f"Use replace_all=True to replace all occurrences.",
                            True
                        )

                # Perform replacement
                if replace_all:
                    count = content.count(old_string)
                    content = content.replace(old_string, new_string)
                else:
                    content = content.replace(old_string, new_string, 1)
                    count = 1

                total_replacements += count

            # Write back to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return (
                f"Successfully applied {len(edits)} edit(s) "
                f"with {total_replacements} total replacement(s) in {file_path}",
                False
            )

        except UnicodeDecodeError:
            return f"Unable to decode file as UTF-8: {file_path}", True
        except PermissionError:
            return f"Permission denied editing file: {file_path}", True
        except Exception as e:
            return f"Error editing file {file_path}: {str(e)}", True

    async def delete_file(self, file_path: str) -> Tuple[str, bool]:
        """Delete a file.

        Args:
            file_path: Path to the file to delete

        Returns:
            Tuple of (success_or_error_message, is_error)
        """
        try:
            path = self._resolve_path(file_path)

            if not path.exists():
                return f"File not found: {file_path}", True

            if not path.is_file():
                return f"Path is not a file: {file_path}", True

            path.unlink()

            return f"Successfully deleted file: {file_path}", False

        except PermissionError:
            return f"Permission denied deleting file: {file_path}", True
        except Exception as e:
            return f"Error deleting file {file_path}: {str(e)}", True

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get raw file content without formatting.

        Args:
            file_path: Path to the file to read

        Returns:
            Raw file content as string, or None if file doesn't exist
        """
        try:
            path = self._resolve_path(file_path)

            if not path.exists() or not path.is_file():
                return None

            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
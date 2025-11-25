"""Docker-based file manager for testing with real filesystem."""

from pathlib import Path
from typing import List, Optional, Tuple

from auto_promptimiser.core.file_manager import BaseFileManager
from tests.scenarios.misc.async_docker_manager import AsyncDockerContainerManager


class DockerFileManager(BaseFileManager):
    """File manager that operates on files inside a Docker container.

    This allows testing with a real filesystem while maintaining isolation.
    """

    def __init__(
        self,
        docker_manager: AsyncDockerContainerManager,
        container_id: str,
        root_dir: Optional[Path] = None
    ):
        """Initialize with a Docker container reference.

        Args:
            docker_manager: The Docker container manager
            container_id: ID of the container to operate on
            root_dir: Working directory inside the container (defaults to /workspace)
        """
        super().__init__(root_dir=root_dir or Path("/workspace"))
        self.docker_manager = docker_manager
        self.container_id = container_id

    def _resolve_path(self, file_path: str) -> str:
        """Resolve a file path relative to root_dir."""
        path = Path(file_path)

        if path.is_absolute():
            return str(path)

        if self.root_dir is not None:
            return str(self.root_dir / path)

        return file_path

    async def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, bool]:
        """Read file contents from the Docker container."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Check if file exists
            check_cmd = f"test -f {resolved_path} && echo 'exists' || echo 'not_found'"
            stdout, _ = await self.docker_manager.execute_command(
                self.container_id,
                check_cmd,
                timeout=5
            )

            if stdout.strip() != 'exists':
                return f"File not found: {file_path}", True

            # Read the file with optional offset/limit
            if offset is not None or limit is not None:
                # Use tail/head for offset/limit
                cmd_parts = [f"cat {resolved_path}"]

                if offset is not None:
                    # tail -n +N starts from line N (1-indexed)
                    cmd_parts.append(f"tail -n +{offset + 1}")

                if limit is not None:
                    cmd_parts.append(f"head -n {limit}")

                read_cmd = " | ".join(cmd_parts)
            else:
                read_cmd = f"cat {resolved_path}"

            stdout, stderr = await self.docker_manager.execute_command(
                self.container_id,
                read_cmd,
                timeout=30
            )

            if stderr:
                return f"Error reading file {file_path}: {stderr}", True

            return stdout, False

        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}", True

    async def write_file(self, file_path: str, content: str) -> Tuple[str, bool]:
        """Write content to a file in the Docker container."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Create parent directories
            parent_dir = str(Path(resolved_path).parent)
            mkdir_cmd = f"mkdir -p {parent_dir}"
            await self.docker_manager.execute_command(
                self.container_id,
                mkdir_cmd,
                timeout=10
            )

            # Write content using cat with heredoc
            # Escape content to avoid issues with quotes and special chars
            import base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
            write_cmd = f"echo '{encoded_content}' | base64 -d > {resolved_path}"

            stdout, stderr = await self.docker_manager.execute_command(
                self.container_id,
                write_cmd,
                timeout=30
            )

            if stderr and "warning" not in stderr.lower():
                return f"Error writing to file {file_path}: {stderr}", True

            return f"Successfully wrote to file: {file_path}", False

        except Exception as e:
            return f"Error writing to file {file_path}: {str(e)}", True

    async def edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> Tuple[str, bool]:
        """Edit file by replacing strings in the Docker container."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Check if file exists
            check_cmd = f"test -f {resolved_path} && echo 'exists' || echo 'not_found'"
            stdout, _ = await self.docker_manager.execute_command(
                self.container_id,
                check_cmd,
                timeout=5
            )

            if stdout.strip() != 'exists':
                return f"File not found: {file_path}", True

            # Read current content
            content, is_error = await self.read_file(file_path)
            if is_error:
                return content, is_error

            # Check if old_string exists
            if old_string not in content:
                return f"String not found in file: {file_path}", True

            # Check uniqueness if not replace_all
            if not replace_all:
                count = content.count(old_string)
                if count > 1:
                    return (
                        f"String appears {count} times in file. "
                        f"Use replace_all=True to replace all occurrences.",
                        True
                    )

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            # Write back
            write_result, is_error = await self.write_file(file_path, new_content)
            if is_error:
                return write_result, is_error

            return f"Successfully replaced {count} occurrence(s) in {file_path}", False

        except Exception as e:
            return f"Error editing file {file_path}: {str(e)}", True

    async def multi_edit_file(
        self,
        file_path: str,
        edits: List[Tuple[str, str, bool]]
    ) -> Tuple[str, bool]:
        """Perform multiple edits on a file in the Docker container."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Check if file exists
            check_cmd = f"test -f {resolved_path} && echo 'exists' || echo 'not_found'"
            stdout, _ = await self.docker_manager.execute_command(
                self.container_id,
                check_cmd,
                timeout=5
            )

            if stdout.strip() != 'exists':
                return f"File not found: {file_path}", True

            if not edits:
                return "No edits provided", True

            # Read current content
            content, is_error = await self.read_file(file_path)
            if is_error:
                return content, is_error

            # Apply each edit sequentially
            total_replacements = 0
            for i, (old_string, new_string, replace_all) in enumerate(edits, 1):
                if old_string not in content:
                    return (
                        f"Edit {i}/{len(edits)} failed: "
                        f"String not found in file: {file_path}",
                        True
                    )

                if not replace_all:
                    count = content.count(old_string)
                    if count > 1:
                        return (
                            f"Edit {i}/{len(edits)} failed: "
                            f"String appears {count} times in file. "
                            f"Use replace_all=True to replace all occurrences.",
                            True
                        )

                if replace_all:
                    count = content.count(old_string)
                    content = content.replace(old_string, new_string)
                else:
                    content = content.replace(old_string, new_string, 1)
                    count = 1

                total_replacements += count

            # Write back
            write_result, is_error = await self.write_file(file_path, content)
            if is_error:
                return write_result, is_error

            return (
                f"Successfully applied {len(edits)} edit(s) "
                f"with {total_replacements} total replacement(s) in {file_path}",
                False
            )

        except Exception as e:
            return f"Error editing file {file_path}: {str(e)}", True

    async def delete_file(self, file_path: str) -> Tuple[str, bool]:
        """Delete a file in the Docker container."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Check if file exists
            check_cmd = f"test -f {resolved_path} && echo 'exists' || echo 'not_found'"
            stdout, _ = await self.docker_manager.execute_command(
                self.container_id,
                check_cmd,
                timeout=5
            )

            if stdout.strip() != 'exists':
                return f"File not found: {file_path}", True

            # Delete the file
            delete_cmd = f"rm {resolved_path}"
            stdout, stderr = await self.docker_manager.execute_command(
                self.container_id,
                delete_cmd,
                timeout=10
            )

            if stderr:
                return f"Error deleting file {file_path}: {stderr}", True

            return f"Successfully deleted file: {file_path}", False

        except Exception as e:
            return f"Error deleting file {file_path}: {str(e)}", True

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get raw file content without formatting."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Check if file exists
            check_cmd = f"test -f {resolved_path} && echo 'exists' || echo 'not_found'"
            stdout, _ = await self.docker_manager.execute_command(
                self.container_id,
                check_cmd,
                timeout=5
            )

            if stdout.strip() != 'exists':
                return None

            # Read the file content
            read_cmd = f"cat {resolved_path}"
            stdout, stderr = await self.docker_manager.execute_command(
                self.container_id,
                read_cmd,
                timeout=30
            )

            if stderr:
                return None

            return stdout

        except Exception:
            return None

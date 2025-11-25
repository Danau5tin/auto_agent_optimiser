"""Docker-based bash executor for testing with real command execution."""

from pathlib import Path
from typing import Optional, Tuple

from auto_promptimiser.core.bash_executor import BaseBashExecutor
from tests.scenarios.misc.async_docker_manager import AsyncDockerContainerManager


class DockerBashExecutor(BaseBashExecutor):
    """Bash executor that runs commands inside a Docker container.

    This allows testing with real bash execution while maintaining isolation.
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
            container_id: ID of the container to execute commands in
            root_dir: Working directory inside the container (defaults to /workspace)
        """
        super().__init__(root_dir=root_dir or Path("/workspace"))
        self.docker_manager = docker_manager
        self.container_id = container_id

    async def execute(
        self,
        command: str,
        block: bool = True,
        timeout_secs: int = 1,
    ) -> Tuple[str, bool]:
        """Execute a bash command in the Docker container.

        Args:
            command: The bash command to execute
            block: Whether to wait for command completion (non-blocking not supported)
            timeout_secs: Maximum time to wait for command completion (seconds)

        Returns:
            Tuple of (output_or_error_message, is_error)
        """
        try:
            if not block:
                return (
                    "Non-blocking execution not supported in DockerBashExecutor",
                    True
                )

            # Execute command with working directory
            exec_kwargs = {}
            if self.root_dir:
                exec_kwargs['workdir'] = str(self.root_dir)

            stdout, stderr = await self.docker_manager.execute_command(
                self.container_id,
                command,
                timeout=timeout_secs,
                **exec_kwargs
            )

            # Combine stdout and stderr
            output = []
            if stdout:
                output.append(stdout)
            if stderr:
                output.append(f"STDERR:\n{stderr}")

            combined_output = "\n".join(output) if output else "(no output)"

            # Docker exec doesn't return exit codes directly, so we check for errors
            # in stderr. This is a simplified approach - might need refinement.
            is_error = bool(stderr and any(
                error_indicator in stderr.lower()
                for error_indicator in ["error", "failed", "cannot", "no such"]
            ))

            return combined_output, is_error

        except Exception as e:
            return f"Error executing command '{command}': {str(e)}", True

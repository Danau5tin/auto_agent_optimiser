"""Concrete implementation of bash command execution for local environment."""

import asyncio
from typing import Tuple

from auto_promptimiser.core.bash_executor import BaseBashExecutor


class LocalBashExecutor(BaseBashExecutor):
    """Bash executor implementation for local command execution."""

    async def execute(
        self,
        command: str,
        block: bool = True,
        timeout_secs: int = 1,
    ) -> Tuple[str, bool]:
        """Execute a bash command.

        Args:
            command: The bash command to execute
            block: Whether to wait for command completion
            timeout_secs: Maximum time to wait for command completion (seconds)

        Returns:
            Tuple of (output_or_error_message, is_error)
        """
        try:
            # Create subprocess with optional working directory
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.root_dir) if self.root_dir else None,
            )

            if not block:
                return f"Command started in background (PID: {process.pid})", False

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_secs
                )
            except asyncio.TimeoutError:
                # Kill the process if it times out
                process.kill()
                await process.wait()
                return (
                    f"Command timed out after {timeout_secs} seconds: {command}",
                    True,
                )

            # Decode output
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""

            # Combine stdout and stderr
            output = []
            if stdout_text:
                output.append(stdout_text)
            if stderr_text:
                output.append(f"STDERR:\n{stderr_text}")

            combined_output = "\n".join(output) if output else "(no output)"

            # Check return code
            if process.returncode != 0:
                return (
                    f"Command failed with exit code {process.returncode}:\n{combined_output}",
                    True,
                )

            return combined_output, False

        except Exception as e:
            return f"Error executing command '{command}': {str(e)}", True

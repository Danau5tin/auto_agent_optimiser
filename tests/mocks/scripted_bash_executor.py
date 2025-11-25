"""Scripted bash executor for testing."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from auto_promptimiser.core.bash_executor import BaseBashExecutor


class ScriptedBashExecutor(BaseBashExecutor):
    """Bash executor that returns predefined outputs for commands.

    Useful for testing scenarios where you want to:
    - Control exact command outputs
    - Simulate specific system states (test failures, build errors, etc.)
    - Track all commands executed
    """

    def __init__(
        self,
        command_responses: Optional[Dict[str, Tuple[str, bool]]] = None,
        root_dir: Optional[Path] = None
    ):
        """Initialize with scripted responses.

        Args:
            command_responses: Dict mapping command strings to (output, is_error) tuples.
                              Supports exact matches and prefix matches (ending with *)
            root_dir: Working directory for commands
        """
        super().__init__(root_dir=root_dir)
        self.command_responses = command_responses or {}
        self.execution_log: List[Dict] = []
        self.default_response: Tuple[str, bool] = ("Bash not usable for now", False)

    async def execute(
        self,
        command: str,
        block: bool = True,
        timeout_secs: int = 1,
    ) -> Tuple[str, bool]:
        self.execution_log.append({
            "command": command,
            "block": block,
            "timeout_secs": timeout_secs
        })

        # Try exact match first
        if command in self.command_responses:
            return self.command_responses[command]

        # Try prefix matches (commands ending with *)
        for pattern, response in self.command_responses.items():
            if pattern.endswith("*") and command.startswith(pattern[:-1]):
                return response

        # Return default if no match found
        return self.default_response

    def set_response(self, command: str, output: str, is_error: bool = False) -> None:
        """Set response for a specific command."""
        self.command_responses[command] = (output, is_error)

    def set_default_response(self, output: str, is_error: bool = False) -> None:
        """Set default response for unmatched commands."""
        self.default_response = (output, is_error)

    def get_executed_commands(self) -> List[str]:
        """Get list of all commands that were executed."""
        return [log["command"] for log in self.execution_log]

    def was_command_executed(self, command: str) -> bool:
        """Check if a specific command was executed (exact match)."""
        return command in self.get_executed_commands()

    def was_command_pattern_executed(self, pattern: str) -> bool:
        """Check if a command matching pattern was executed (substring match)."""
        return any(pattern in cmd for cmd in self.get_executed_commands())

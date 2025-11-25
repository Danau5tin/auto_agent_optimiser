"""Abstract base class for bash command execution."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple


class BaseBashExecutor(ABC):
    """Abstract base class for executing bash commands in different environments."""

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize bash executor with optional root directory.

        Args:
            root_dir: Root directory for command execution. Commands will be executed
                     with this directory as the working directory.
        """
        self.root_dir = root_dir

    @abstractmethod
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

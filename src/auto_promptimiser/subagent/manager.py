"""Manager for tracking active subagents across an iteration."""

import logging
import random
from typing import Dict, Optional

from auto_promptimiser.subagent.subagent import SubAgent

logger = logging.getLogger(__name__)

# Word lists for generating memorable subagent IDs
_ADJECTIVES = [
    "swift", "bright", "calm", "bold", "keen", "warm", "cool", "quick",
    "sharp", "soft", "wild", "wise", "gold", "silver", "red", "blue",
    "green", "dark", "light", "fresh", "snap", "crisp", "prime", "grand",
]

_NOUNS = [
    "pony", "wolf", "hawk", "bear", "fox", "owl", "deer", "lion",
    "tiger", "eagle", "raven", "spark", "storm", "river", "flame", "frost",
    "stone", "cloud", "star", "moon", "wind", "wave", "peak", "brook",
]


class SubAgentManager:
    """Manages the lifecycle of active subagents.

    Subagents are tracked by a unique ID and can be messaged until they are
    disposed (typically at the end of an iteration).
    """

    def __init__(self):
        self._active_subagents: Dict[str, SubAgent] = {}

    def _generate_unique_id(self) -> str:
        """Generate a unique two-word ID like 'snap-pony'."""
        while True:
            subagent_id = f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"
            if subagent_id not in self._active_subagents:
                return subagent_id

    def register(self, subagent: SubAgent) -> str:
        """Register a subagent and return its unique ID.

        Args:
            subagent: The subagent instance to register

        Returns:
            A unique string ID for referencing this subagent
        """
        subagent_id = self._generate_unique_id()
        self._active_subagents[subagent_id] = subagent
        logger.info(f"Registered subagent {subagent_id} (type: {subagent.subagent_type})")
        return subagent_id

    def get(self, subagent_id: str) -> Optional[SubAgent]:
        """Get a subagent by ID.

        Args:
            subagent_id: The ID of the subagent

        Returns:
            The SubAgent instance if found, None otherwise
        """
        return self._active_subagents.get(subagent_id)

    def dispose(self, subagent_id: str) -> bool:
        """Dispose of a specific subagent.

        Args:
            subagent_id: The ID of the subagent to dispose

        Returns:
            True if the subagent was found and disposed, False otherwise
        """
        if subagent_id in self._active_subagents:
            del self._active_subagents[subagent_id]
            logger.info(f"Disposed subagent {subagent_id}")
            return True
        return False

    def dispose_all(self) -> int:
        """Dispose of all active subagents.

        Returns:
            The number of subagents that were disposed
        """
        count = len(self._active_subagents)
        if count > 0:
            logger.info(f"Disposing {count} active subagent(s)")
            self._active_subagents.clear()
        return count

    def list_active_ids(self) -> list[str]:
        """Get a list of all active subagent IDs.

        Returns:
            List of active subagent IDs
        """
        return list(self._active_subagents.keys())

    @property
    def active_count(self) -> int:
        """Get the number of active subagents."""
        return len(self._active_subagents)

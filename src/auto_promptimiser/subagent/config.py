"""Configuration mapping for different subagent types."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Type

from auto_promptimiser.core.action import Action
from auto_promptimiser.agent.actions.bash import BashAction
from auto_promptimiser.agent.actions.file_actions import (
    ReadAction,
    WriteAction,
    EditAction,
    MultiEditAction,
)
from auto_promptimiser.agent.actions.report import ReportAction
from auto_promptimiser.agent.actions.respond import RespondAction

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class SubAgentConfig:
    """Configuration for a subagent type."""
    system_message_file: str
    available_action_map: Dict[str, Type[Action]]

    def load_system_message(self) -> str:
        """Load and return the system message content."""
        filepath = PROMPTS_DIR / self.system_message_file

        if not filepath.exists():
            raise FileNotFoundError(
                f"System message file not found: {filepath}"
            )

        with open(filepath, "r") as f:
            return f.read().strip()


SUBAGENT_CONFIG_MAP: Dict[str, SubAgentConfig] = {
    "trajectory_analysis_agent": SubAgentConfig(
        system_message_file="trajectory_analysis_agent.md",
        available_action_map={
            "read": ReadAction,
            "report": ReportAction,
            "respond": RespondAction,
        },
    ),
}


def get_config_for_type(subagent_type: str) -> SubAgentConfig:
    if subagent_type not in SUBAGENT_CONFIG_MAP:
        raise ValueError(
            f"Unknown subagent type: {subagent_type}. "
            f"Available types: {list(SUBAGENT_CONFIG_MAP.keys())}"
        )

    return SUBAGENT_CONFIG_MAP[subagent_type]

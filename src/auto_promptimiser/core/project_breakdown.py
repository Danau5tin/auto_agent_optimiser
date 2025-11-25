"""Data structures and utilities for project breakdown configuration."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ActionParameter:
    """Represents a parameter for an available action."""
    type: str
    description: str
    options: list[str] | None = None


@dataclass
class AvailableAction:
    """Represents an action available to the target agent."""
    description: str
    parameters: dict[str, ActionParameter]


@dataclass
class KeyFile:
    """Represents a key file in the target system."""
    description: str


@dataclass
class EditingGuideline:
    """Represents an editing guideline for the target system."""
    description: str


@dataclass
class KnownLimitation:
    """Represents an eval that has been identified as not worth pursuing."""
    eval_name: str
    reason: str


@dataclass
class ProjectBreakdown:
    """Represents the complete project breakdown configuration."""
    key_files: dict[str, KeyFile]
    available_actions: dict[str, AvailableAction]
    editing_guidelines: dict[str, EditingGuideline]
    known_limitations: dict[str, KnownLimitation]
    _raw_yaml: str
    _file_path: Path | None = None

    def to_str(self) -> str:
        """Return string representation including dynamically added known limitations."""
        result = self._raw_yaml

        if self.known_limitations:
            result += "\nknown_limitations:\n"
            for eval_name, limitation in self.known_limitations.items():
                result += f"  {eval_name}:\n"
                result += f"    reason: {limitation.reason}\n"

        return result

    def actions_to_str(self) -> str:
        """Return a string representation of available actions."""
        action_strs = []
        for action_name, action in self.available_actions.items():
            params_str = ", ".join(
                f"{param_name} ({param.type})"
                for param_name, param in action.parameters.items()
            )
            action_strs.append(f"- {action_name}: {action.description} [Params: {params_str}]")
        return "\n".join(action_strs)

    def update_file(self, filepath: str, description: str) -> None:
        """Add or update a file entry."""
        self.key_files[filepath] = KeyFile(description=description)

    def update_action(self, action_name: str, description: str) -> None:
        """Add or update an action entry."""
        if action_name in self.available_actions:
            # Keep existing parameters, just update description
            self.available_actions[action_name].description = description
        else:
            # New action with no parameters (will need to be manually configured)
            self.available_actions[action_name] = AvailableAction(
                description=description,
                parameters={}
            )

    def add_known_limitation(self, eval_name: str, reason: str) -> None:
        """Mark an eval as a known limitation that should not be pursued further."""
        self.known_limitations[eval_name] = KnownLimitation(
            eval_name=eval_name,
            reason=reason
        )

    def _clone_data(self) -> tuple[
        dict[str, KeyFile],
        dict[str, AvailableAction],
        dict[str, EditingGuideline],
        dict[str, KnownLimitation],
    ]:
        """Clone all mutable data structures for copy/restore operations."""
        key_files = {k: KeyFile(description=v.description) for k, v in self.key_files.items()}
        available_actions = {
            k: AvailableAction(
                description=v.description,
                parameters={
                    pk: ActionParameter(
                        type=pv.type,
                        description=pv.description,
                        options=list(pv.options) if pv.options else None,
                    )
                    for pk, pv in v.parameters.items()
                },
            )
            for k, v in self.available_actions.items()
        }
        editing_guidelines = {
            k: EditingGuideline(description=v.description)
            for k, v in self.editing_guidelines.items()
        }
        known_limitations = {
            k: KnownLimitation(eval_name=v.eval_name, reason=v.reason)
            for k, v in self.known_limitations.items()
        }
        return key_files, available_actions, editing_guidelines, known_limitations

    def copy(self) -> 'ProjectBreakdown':
        """Create a deep copy of this ProjectBreakdown."""
        key_files, available_actions, editing_guidelines, known_limitations = self._clone_data()
        return ProjectBreakdown(
            key_files=key_files,
            available_actions=available_actions,
            editing_guidelines=editing_guidelines,
            known_limitations=known_limitations,
            _raw_yaml=self._raw_yaml,
            _file_path=self._file_path,
        )

    def restore_from(self, other: 'ProjectBreakdown') -> None:
        """Restore this breakdown's state from another breakdown."""
        key_files, available_actions, editing_guidelines, known_limitations = other._clone_data()
        self.key_files = key_files
        self.available_actions = available_actions
        self.editing_guidelines = editing_guidelines
        self.known_limitations = known_limitations
        self._raw_yaml = other._raw_yaml
        self._file_path = other._file_path


def load_project_breakdown(file_path: str | Path) -> ProjectBreakdown:
    """
    Load project breakdown from a YAML file.

    Args:
        file_path: Path to the project_breakdown.yaml file

    Returns:
        ProjectBreakdown object with structured data

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the YAML is malformed
        ValueError: If required fields are missing
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Project breakdown file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    data = yaml.safe_load(raw_content)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML root to be a dict, got {type(data)}")

    # Parse key_files
    key_files_data = data.get("key_files", {})
    key_files = {
        file_name: KeyFile(description=file_info["description"])
        for file_name, file_info in key_files_data.items()
    }

    # Parse available_actions
    actions_data = data.get("available_actions", {})
    available_actions = {}
    for action_name, action_info in actions_data.items():
        params_data = action_info.get("parameters", {})
        parameters = {}
        for param_name, param_info in params_data.items():
            parameters[param_name] = ActionParameter(
                type=param_info["type"],
                description=param_info["description"],
                options=param_info.get("options"),
            )
        available_actions[action_name] = AvailableAction(
            description=action_info["description"],
            parameters=parameters,
        )

    # Parse editing_guidelines
    guidelines_data = data.get("editing_guidelines", {})
    editing_guidelines = {
        guideline_name: EditingGuideline(description=guideline_info["description"])
        for guideline_name, guideline_info in guidelines_data.items()
    }

    # Parse known_limitations (may not exist in file, added dynamically during optimization)
    limitations_data = data.get("known_limitations", {})
    known_limitations = {
        eval_name: KnownLimitation(eval_name=eval_name, reason=limit_info["reason"])
        for eval_name, limit_info in limitations_data.items()
    }

    return ProjectBreakdown(
        key_files=key_files,
        available_actions=available_actions,
        editing_guidelines=editing_guidelines,
        known_limitations=known_limitations,
        _raw_yaml=raw_content,
        _file_path=path,
    )

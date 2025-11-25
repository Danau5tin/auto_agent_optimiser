from abc import ABC, abstractmethod
from typing import Dict, Generic, List, Tuple, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class BaseParser(ABC, Generic[T]):
    """Base class for parsing LLM responses into structured action objects.

    Subclasses implement specific parsing strategies (XML/YAML, JSON, etc.)
    while maintaining a consistent interface for action extraction and validation.
    """

    def __init__(
        self,
        mapping_tag_to_action_class: Dict[str, type[T]],
        ignored_tags: List[str] = None,
    ):
        """Initialize the parser with action mappings.

        Args:
            mapping_tag_to_action_class: Maps action type identifiers to their Pydantic model classes
            ignored_tags: List of tag/action types to skip during parsing
        """
        self.ignored_tags = ignored_tags or []
        self.mapping_tag_to_action_class = mapping_tag_to_action_class

    def parse_actions(self, response: str) -> Tuple[List[T], List[str], bool]:
        """Parse actions from an LLM response string.

        Args:
            response: The raw LLM response text

        Returns:
            Tuple of (actions, errors, found_action_attempt) where:
                - actions: List of successfully parsed and validated action objects
                - errors: List of error messages from parsing/validation failures
                - found_action_attempt: True if any action tags were detected
        """
        actions = []
        errors = []
        found_action_attempt = False

        for action_type, content in self._extract_action_data(response):
            if action_type.lower() in self.ignored_tags:
                continue

            found_action_attempt = True
            try:
                action = self._parse_single_action(action_type, content)
                actions.append(action)

            except ValueError as e:
                errors.append(f"[{action_type}] Validation error: {e}")
            except Exception as e:
                errors.append(f"[{action_type}] Unexpected error: {e}")

        return actions, errors, found_action_attempt

    @abstractmethod
    def _extract_action_data(self, response: str) -> List[Tuple[str, str]]:
        """Extract action type and content pairs from the response.

        Args:
            response: The raw LLM response text

        Returns:
            List of (action_type, content) tuples
        """
        pass

    @abstractmethod
    def _parse_single_action(self, action_type: str, content: str) -> T:
        """Parse and validate a single action from its content.

        Args:
            action_type: The identifier for this action type
            content: The raw content to parse

        Returns:
            Validated action object

        Raises:
            ValueError: If validation fails
            Exception: For other parsing errors
        """
        pass

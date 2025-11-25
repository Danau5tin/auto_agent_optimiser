import json
import re
from typing import Any, Dict, List, Tuple

from auto_promptimiser.core.base_parser import BaseParser, T


class JSONParser(BaseParser[T]):
    """Parser for JSON-formatted actions.

    Supports multiple formats:
    1. Individual JSON objects (one per line or separated):
       {"action_type": "bash", "command": "ls"}
       {"action_type": "read", "file_path": "/path"}

    2. JSON array of objects:
       [
         {"action_type": "bash", "command": "ls"},
         {"action_type": "read", "file_path": "/path"}
       ]

    Each JSON object must have an action_type field that maps to an action class.
    """

    def __init__(
        self,
        mapping_tag_to_action_class: Dict[str, type[T]],
        ignored_tags: List[str] = None,
        action_type_field: str = "action_type",
    ):
        """Initialize the JSON parser.

        Args:
            mapping_tag_to_action_class: Maps action type identifiers to their Pydantic model classes
            ignored_tags: List of action types to skip during parsing
            action_type_field: Name of the field that identifies the action type (default: "action_type")
        """
        super().__init__(mapping_tag_to_action_class, ignored_tags or [])
        self.action_type_field = action_type_field

    def _extract_action_data(self, response: str) -> List[Tuple[str, str]]:
        """Extract JSON objects from response.

        Returns list of (action_type, json_string) tuples.
        """
        # Remove markdown code fences
        cleaned = re.sub(r'```(?:json)?\s*', '', response).strip()

        # Try parsing as complete JSON first
        try:
            data = json.loads(cleaned)
            return self._process_json_data(data)
        except json.JSONDecodeError:
            pass

        # Fall back to finding individual JSON objects
        return self._extract_json_objects(cleaned)

    def _process_json_data(self, data: Any) -> List[Tuple[str, str]]:
        """Process parsed JSON data into action tuples."""
        results = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and self.action_type_field in item:
                    action_type = item[self.action_type_field]
                    results.append((action_type, json.dumps(item)))
        elif isinstance(data, dict) and self.action_type_field in data:
            action_type = data[self.action_type_field]
            results.append((action_type, json.dumps(data)))

        return results

    def _extract_json_objects(self, text: str) -> List[Tuple[str, str]]:
        """Extract multiple JSON objects from text."""
        results = []
        decoder = json.JSONDecoder()
        idx = 0

        while idx < len(text):
            # Skip whitespace
            while idx < len(text) and text[idx].isspace():
                idx += 1

            if idx >= len(text):
                break

            try:
                obj, end_idx = decoder.raw_decode(text, idx)

                # Process the decoded object
                if isinstance(obj, list):
                    results.extend(self._process_json_data(obj))
                elif isinstance(obj, dict) and self.action_type_field in obj:
                    action_type = obj[self.action_type_field]
                    results.append((action_type, json.dumps(obj)))

                idx = end_idx
            except json.JSONDecodeError:
                idx += 1

        return results

    def _parse_single_action(self, action_type: str, content: str) -> T:
        """Parse JSON content and validate against action class."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON decode error: {e}")

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")

        action_class = self.mapping_tag_to_action_class.get(action_type.lower())
        if not action_class:
            raise ValueError(f"Unknown action type: {action_type}")

        # Remove the action_type field before validation since it's not part of the action model
        data_copy = data.copy()
        data_copy.pop(self.action_type_field, None)

        return action_class.model_validate(data_copy)

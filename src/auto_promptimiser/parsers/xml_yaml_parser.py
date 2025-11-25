import re
from textwrap import dedent
from typing import Dict, List, Tuple

import yaml

from auto_promptimiser.core.base_parser import BaseParser, T


class XmlYamlParser(BaseParser[T]):
    """Parser for XML-tagged actions with YAML content.

    Extracts actions from XML tags like:
    <action_name>
    field1: value1
    field2: value2
    </action_name>
    """

    def __init__(
        self,
        mapping_tag_to_action_class: Dict[str, type[T]],
        ignored_tags: List[str] = None,
    ):
        if ignored_tags is None:
            ignored_tags = ["think"]
        super().__init__(mapping_tag_to_action_class, ignored_tags)

    def _extract_action_data(self, response: str) -> List[Tuple[str, str]]:
        """Extract XML tag pairs from response."""
        # Match top-level tags (not nested)
        pattern = r"(?:^|\n)\s*<(\w+)>([\s\S]*?)</\1>"
        matches = re.findall(pattern, response, re.MULTILINE)
        return matches

    def _parse_single_action(self, action_type: str, content: str) -> T:
        """Parse YAML content and validate against action class."""
        try:
            # Dedent first to remove common indentation, then strip whitespace
            data = yaml.safe_load(dedent(content).strip())
        except yaml.YAMLError as e:
            raise ValueError(f"YAML error: {e}")

        action_class = self.mapping_tag_to_action_class.get(action_type.lower())
        if not action_class:
            raise ValueError(f"Unknown action type: {action_type}")

        return action_class.model_validate(data)

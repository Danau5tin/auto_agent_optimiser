"""Tests for base parser, XmlYamlParser, and JSONParser."""
import pytest
from pydantic import BaseModel

from auto_promptimiser.agent.actions.eval_actions import EndIterationAction, RunEvalSuiteAction
from auto_promptimiser.agent.actions.file_actions import EditAction, ReadAction
from auto_promptimiser.core.action import Action
from auto_promptimiser.parsers.json_parser import JSONParser
from auto_promptimiser.parsers.xml_yaml_parser import XmlYamlParser


class SampleAction(BaseModel):
    command: str
    arg: int


class TestXmlYamlParser:
    def test_parse_single_action(self):
        parser = XmlYamlParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction}
        )

        response = """
        <test>
        command: hello
        arg: 42
        </test>
        """

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1
        assert len(errors) == 0
        assert found is True
        assert actions[0].command == "hello"
        assert actions[0].arg == 42

    def test_parse_multiple_actions(self):
        parser = XmlYamlParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction}
        )

        response = """
        <test>
        command: first
        arg: 1
        </test>

        <test>
        command: second
        arg: 2
        </test>
        """

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 2
        assert len(errors) == 0
        assert actions[0].command == "first"
        assert actions[1].command == "second"

    def test_ignored_tags(self):
        parser = XmlYamlParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction},
            ignored_tags=["think"]
        )

        response = """
        <think>
        This should be ignored
        </think>

        <test>
        command: hello
        arg: 42
        </test>
        """

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1
        assert actions[0].command == "hello"


class TestJSONParser:
    def test_parse_single_json_object(self):
        parser = JSONParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction}
        )

        response = '{"action_type": "test", "command": "hello", "arg": 42}'

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1
        assert len(errors) == 0
        assert found is True
        assert actions[0].command == "hello"
        assert actions[0].arg == 42

    def test_parse_json_array(self):
        parser = JSONParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction}
        )

        response = '''[
            {"action_type": "test", "command": "first", "arg": 1},
            {"action_type": "test", "command": "second", "arg": 2}
        ]'''

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 2
        assert len(errors) == 0
        assert actions[0].command == "first"
        assert actions[1].command == "second"

    def test_parse_multiple_json_objects(self):
        parser = JSONParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction}
        )

        response = '''
        {"action_type": "test", "command": "first", "arg": 1}
        {"action_type": "test", "command": "second", "arg": 2}
        '''

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 2
        assert actions[0].command == "first"
        assert actions[1].command == "second"

    def test_custom_action_type_field(self):
        parser = JSONParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction},
            action_type_field="type"
        )

        response = '{"type": "test", "command": "hello", "arg": 42}'

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1
        assert actions[0].command == "hello"
        assert actions[0].arg == 42

    def test_ignored_tags(self):
        parser = JSONParser[SampleAction](
            mapping_tag_to_action_class={"test": SampleAction},
            ignored_tags=["think"]
        )

        response = '''[
            {"action_type": "think", "command": "ignore", "arg": 0},
            {"action_type": "test", "command": "hello", "arg": 42}
        ]'''

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1
        assert actions[0].command == "hello"

    def test_end_action_found(self):
        parser = JSONParser[Action](
            mapping_tag_to_action_class={"end_iteration": EndIterationAction}
        )

        response = '```{\n  "action_type": "end_iteration",\n  "changelog_entry": "Fixed critical bug in calculator_tool.py line 3: changed \'return a + b * 9\' to \'return a + b\' to correctly implement addition operation.",\n  "project_breakdown_updates": {\n    "files": {\n      "calculator_tool.py": "The implementation of the calculator tool with corrected addition operation"\n    },\n    "actions": {}\n  }\n}\n```'

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1

    def test_edit_action_found(self):
        parser = JSONParser[Action](
            mapping_tag_to_action_class={"edit": EditAction}
        )

        response = '```json\n{\n  "action_type": "edit",\n  "file_path": "calculator_tool.py",\n  "old_string": "    if operation == \\"add\\":\\n        return a + b * 9",\n  "new_string": "    if operation == \\"add\\":\\n        return a + b",\n  "replace_all": false\n}\n```'

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1

    def test_edit_action_found_noisy(self):
        parser = JSONParser[Action](
            mapping_tag_to_action_class={"edit": EditAction}
        )

        response = """I found the bug! In the calculate function, when performing addition, b is being multiplied by 9 due to operator precedence:
`return a + b * 9`

This is why 5 + 7 becomes 5 + (7 * 9) = 5 + 63 = 68. Let me fix this.

{"action_type": "edit", "file_path": "calculator_tool.py", "old_string": "        return a + b * 9", "new_string": "        return a + b"}
"""
        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1

    def test_run_evals_found(self):
        parser = JSONParser[Action](
            mapping_tag_to_action_class={"run_eval_suite": RunEvalSuiteAction}
        )

        response = """I've fixed the bug. Now let me run the evaluation suite to verify the fix works.

{"action_type": "run_eval_suite", "evals_to_run": ["all"]}
"""
        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 1

    def test_three_read_action_found_in_noisy_output(self):
        parser = JSONParser[Action](
            mapping_tag_to_action_class={"read": ReadAction}
        )

        response = 'I\'ll start by reading the relevant files to understand the current implementation and then analyze why the basic_addition_test is failing.\n\n```json\n[\n  {"action_type": "read", "file_path": "agent.py"},\n  {"action_type": "read", "file_path": "tool_call_entities.py"},\n  {"action_type": "read", "file_path": "calculator_tool.py"}\n]\n```'

        actions, errors, found = parser.parse_actions(response)

        assert len(actions) == 3
        

"""Utility functions for action handlers."""


def format_tool_output(tool_name: str, content: str) -> str:
    tag_name = f"{tool_name}_output"
    return f"<{tag_name}>\n{content}\n</{tag_name}>"

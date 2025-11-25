from pathlib import Path


def load_asset(relative_path: str) -> str:
    """Load an asset file by relative path from the assets directory."""
    assets_dir = Path(__file__).parent
    file_path = assets_dir / relative_path
    return file_path.read_text()


def load_assets(relative_paths: dict[str, str]) -> dict[str, str]:
    """Load multiple asset files.

    Args:
        relative_paths: Mapping of logical name to relative path from assets dir.
                       e.g., {"calculator_tool.py": "calculator_agent/calculator_tool_broken.py"}

    Returns:
        Dictionary mapping logical names to file contents.
    """
    return {name: load_asset(path) for name, path in relative_paths.items()}

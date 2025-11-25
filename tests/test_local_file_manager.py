"""Tests for LocalFileManager class."""

import pytest
from pathlib import Path

from auto_promptimiser.agent.local_tools.local_file_manager import LocalFileManager


@pytest.fixture
def file_manager():
    """Create a LocalFileManager instance for testing."""
    return LocalFileManager()


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file with sample content."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
    return str(file_path)


@pytest.fixture
def temp_dir(tmp_path):
    """Return a temporary directory path."""
    return tmp_path


@pytest.mark.asyncio
async def test_read_file(file_manager, temp_file):
    """Test reading a file successfully."""
    content, is_error = await file_manager.read_file(temp_file)

    assert not is_error
    assert content == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"


@pytest.mark.asyncio
async def test_write_file(file_manager, temp_dir):
    """Test writing content to a file."""
    file_path = str(temp_dir / "new_file.txt")
    test_content = "Hello, World!\nThis is a test."

    message, is_error = await file_manager.write_file(file_path, test_content)

    assert not is_error
    assert "Successfully wrote to file" in message
    assert Path(file_path).read_text() == test_content


@pytest.mark.asyncio
async def test_edit_file(file_manager, temp_file):
    """Test editing a file by replacing a string."""
    old_string = "Line 2"
    new_string = "Second Line"

    message, is_error = await file_manager.edit_file(temp_file, old_string, new_string)

    assert not is_error
    assert "Successfully replaced 1 occurrence(s)" in message

    content = Path(temp_file).read_text()
    assert new_string in content
    assert old_string not in content


@pytest.mark.asyncio
async def test_multi_edit_file(file_manager, temp_file):
    """Test performing multiple edits on a file."""
    edits = [
        ("Line 1", "First Line", False),
        ("Line 2", "Second Line", False),
        ("Line 3", "Third Line", False),
    ]

    message, is_error = await file_manager.multi_edit_file(temp_file, edits)

    assert not is_error
    assert "Successfully applied 3 edit(s)" in message

    content = Path(temp_file).read_text()
    assert "First Line" in content
    assert "Second Line" in content
    assert "Third Line" in content


@pytest.mark.asyncio
async def test_delete_file(file_manager, temp_file):
    """Test deleting a file."""
    message, is_error = await file_manager.delete_file(temp_file)

    assert not is_error
    assert "Successfully deleted file" in message
    assert not Path(temp_file).exists()

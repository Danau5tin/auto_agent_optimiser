"""Tests for LocalBashExecutor class."""

import pytest

from auto_promptimiser.agent.local_tools.local_bash_executor import LocalBashExecutor


@pytest.fixture
def bash_executor():
    """Create a LocalBashExecutor instance for testing."""
    return LocalBashExecutor()


@pytest.mark.asyncio
async def test_execute_simple_command(bash_executor):
    """Test executing a simple command successfully."""
    output, is_error = await bash_executor.execute("echo 'Hello, World!'")

    assert not is_error
    assert "Hello, World!" in output


@pytest.mark.asyncio
async def test_execute_command_with_output(bash_executor):
    """Test executing a command that produces output."""
    output, is_error = await bash_executor.execute("ls /")

    assert not is_error
    assert len(output) > 0


@pytest.mark.asyncio
async def test_execute_failing_command(bash_executor):
    """Test executing a command that fails."""
    output, is_error = await bash_executor.execute("exit 1")

    assert is_error
    assert "exit code 1" in output


@pytest.mark.asyncio
async def test_execute_nonexistent_command(bash_executor):
    """Test executing a command that doesn't exist."""
    output, is_error = await bash_executor.execute("nonexistentcommand12345")

    assert is_error
    assert "not found" in output.lower() or "exit code" in output.lower()


@pytest.mark.asyncio
async def test_execute_with_timeout(bash_executor):
    """Test executing a command that times out."""
    # Command that sleeps for 2 seconds with 1 second timeout
    output, is_error = await bash_executor.execute("sleep 2", timeout_secs=1)

    assert is_error
    assert "timed out" in output.lower()


@pytest.mark.asyncio
async def test_execute_non_blocking(bash_executor):
    """Test executing a command in non-blocking mode."""
    output, is_error = await bash_executor.execute("sleep 1", block=False)

    assert not is_error
    assert "started in background" in output.lower()
    assert "PID" in output

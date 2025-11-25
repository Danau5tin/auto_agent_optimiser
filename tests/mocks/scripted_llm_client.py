"""Scripted LLM client for testing."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock


class ScriptedLLMClient:
    """LLM client that returns predefined responses in sequence.

    Useful for testing scenarios where you want to:
    - Control exact LLM outputs (agent decisions)
    - Simulate specific agent behaviors
    - Test deterministic scenarios
    """

    def __init__(self, responses: Optional[List[str]] = None):
        """Initialize with scripted responses.

        Args:
            responses: List of LLM responses to return in order.
                      Each call to the mocked get_llm_response will return
                      the next response in the list.
        """
        self.responses = responses or []
        self.call_index = 0
        self.call_log: List[Dict[str, Any]] = []

    def get_mock_function(self) -> AsyncMock:
        """Get an AsyncMock that can replace get_llm_response.

        Usage:
            scripted = ScriptedLLMClient(responses=[...])
            monkeypatch.setattr(
                "auto_promptimiser.core.base_agent.get_llm_response",
                scripted.get_mock_function()
            )
        """
        async def mock_get_llm_response(
            messages: List[Dict[str, Any]],
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: int = 4096,
            api_key: Optional[str] = None,
            api_base: Optional[str] = None,
            **kwargs,
        ) -> str:
            self.call_log.append({
                "messages": messages,
                "model": model,
                "api_key": api_key,
            })

            if self.call_index >= len(self.responses):
                raise IndexError(
                    f"No more scripted responses available. "
                    f"Called {self.call_index + 1} times but only {len(self.responses)} responses provided."
                )

            response = self.responses[self.call_index]
            self.call_index += 1
            return response

        return mock_get_llm_response

    def add_response(self, response: str) -> None:
        """Add a response to the end of the response queue."""
        self.responses.append(response)

    def get_call_count(self) -> int:
        """Get number of times the LLM was called."""
        return self.call_index

    def get_last_messages(self) -> Optional[List[Dict[str, Any]]]:
        """Get the messages from the last LLM call."""
        if not self.call_log:
            return None
        return self.call_log[-1]["messages"]

    def reset(self) -> None:
        """Reset the client to start from the first response."""
        self.call_index = 0
        self.call_log = []

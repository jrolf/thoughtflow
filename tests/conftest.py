"""
Pytest configuration and shared fixtures for ThoughtFlow tests.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


# ============================================================================
# Markers
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (requires API keys)",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow-running",
    )


# ============================================================================
# Skip conditions
# ============================================================================


def skip_if_no_api_key(env_var: str) -> pytest.MarkDecorator:
    """Skip test if an API key environment variable is not set.

    Args:
        env_var: Name of the environment variable to check.

    Returns:
        Pytest skip marker.
    """
    return pytest.mark.skipif(
        not os.getenv(env_var),
        reason=f"{env_var} not set",
    )


skip_if_no_openai = skip_if_no_api_key("OPENAI_API_KEY")
skip_if_no_anthropic = skip_if_no_api_key("ANTHROPIC_API_KEY")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    """Sample message list for testing.

    Returns:
        A simple message list with system and user messages.
    """
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def sample_tool_payload() -> dict[str, Any]:
    """Sample tool payload for testing.

    Returns:
        A simple tool call payload.
    """
    return {
        "operation": "add",
        "a": 5,
        "b": 3,
    }


@pytest.fixture
def mock_adapter_response() -> dict[str, Any]:
    """Mock adapter response for testing.

    Returns:
        A mock response that looks like what an adapter would return.
    """
    return {
        "content": "I'm doing well, thank you for asking!",
        "model": "mock-model",
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 10,
            "total_tokens": 35,
        },
        "finish_reason": "stop",
    }


# ============================================================================
# Mock classes for testing
# ============================================================================


class MockAdapter:
    """A mock adapter for testing without API calls.

    Example:
        >>> adapter = MockAdapter(response="Hello!")
        >>> agent = Agent(adapter)
        >>> response = agent.call(messages)
        >>> assert response == "Hello!"
    """

    def __init__(
        self,
        response: str = "Mock response",
        usage: dict[str, int] | None = None,
    ) -> None:
        """Initialize the mock adapter.

        Args:
            response: The response to return.
            usage: Token usage to report.
        """
        self.response = response
        self.usage = usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mock completion - records the call and returns canned response.

        Args:
            messages: Input messages.
            params: Optional parameters.

        Returns:
            Mock response dict.
        """
        self.calls.append({"messages": messages, "params": params})
        return {
            "content": self.response,
            "model": "mock-model",
            "usage": self.usage,
            "finish_reason": "stop",
        }


@pytest.fixture
def mock_adapter() -> MockAdapter:
    """Provide a mock adapter for testing.

    Returns:
        A MockAdapter instance.
    """
    return MockAdapter()

"""
Pytest configuration and shared fixtures for ThoughtFlow tests.

This module provides shared test fixtures and configuration for the entire
test suite. All fixtures defined here are available to all test files
without explicit import.
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
skip_if_no_groq = skip_if_no_api_key("GROQ_API_KEY")


# ============================================================================
# Core Primitive Fixtures
# ============================================================================


@pytest.fixture
def memory():
    """
    Fresh MEMORY instance for testing.
    
    Provides a clean MEMORY object with no pre-existing state.
    Use this when you need to test MEMORY behavior from a blank slate.
    
    Returns:
        A new MEMORY instance with empty state.
    """
    from thoughtflow import MEMORY
    return MEMORY()


@pytest.fixture
def populated_memory(memory):
    """
    MEMORY with pre-populated state for testing.
    
    Provides a MEMORY object with some standard test data already added:
    - A system message
    - A user message  
    - A variable with description
    
    Use this when you need to test operations that require existing state.
    
    Args:
        memory: The base memory fixture (injected by pytest).
        
    Returns:
        A MEMORY instance with pre-populated test data.
    """
    memory.add_msg('system', 'You are a helpful assistant.', channel='webapp')
    memory.add_msg('user', 'Hello, how are you?', channel='webapp')
    memory.set_var('user_name', 'Alice', desc='The name of the test user')
    memory.set_var('session_count', 1, desc='Number of sessions')
    return memory


# ============================================================================
# Mock LLM Fixtures
# ============================================================================


class MockLLM:
    """
    A mock LLM that returns configurable responses without making HTTP calls.
    
    This mock simulates the LLM class interface for testing THOUGHT operations
    without requiring actual API calls. It tracks all calls made to it for
    verification in tests.
    
    Attributes:
        responses: List of responses to return (cycles through if exhausted).
        call_count: Number of times call() has been invoked.
        calls: List of all call arguments for verification.
        service: Mock service name.
        model: Mock model name.
    
    Example:
        >>> llm = MockLLM(responses=["Hello!", "Goodbye!"])
        >>> llm.call([{"role": "user", "content": "Hi"}])
        ['Hello!']
        >>> llm.call([{"role": "user", "content": "Bye"}])
        ['Goodbye!']
        >>> len(llm.calls)
        2
    """
    
    def __init__(self, responses: list[str] | None = None):
        """
        Initialize the mock LLM.
        
        Args:
            responses: List of responses to return. If None, returns ["Mock response"].
                       Cycles through responses if more calls are made than responses.
        """
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []
        self.service = "mock"
        self.model = "mock-model"
        self.last_params: dict[str, Any] = {}
    
    def call(self, msgs: list[dict[str, Any]], params: dict[str, Any] | None = None) -> list[str]:
        """
        Simulate an LLM call and return the next configured response.
        
        Args:
            msgs: List of message dicts (same format as real LLM).
            params: Optional parameters (stored but not used).
            
        Returns:
            List containing the next response string.
        """
        self.calls.append({'msgs': msgs, 'params': params or {}})
        self.last_params = params or {}
        
        # Get response, cycling if we've exhausted the list
        response_idx = self.call_count % len(self.responses)
        response = self.responses[response_idx]
        self.call_count += 1
        
        return [response]
    
    def reset(self) -> None:
        """Reset the mock to its initial state."""
        self.call_count = 0
        self.calls = []
        self.last_params = {}


@pytest.fixture
def mock_llm():
    """
    Factory fixture for creating MockLLM instances.
    
    Returns a class (not an instance) so tests can configure
    the mock with specific responses.
    
    Example:
        def test_something(mock_llm):
            llm = mock_llm(responses=["Expected output"])
            # Use llm in test...
    
    Returns:
        The MockLLM class for instantiation.
    """
    return MockLLM


@pytest.fixture
def mock_llm_instance():
    """
    A pre-instantiated MockLLM with default responses.
    
    Use this when you don't need custom responses and just want
    a working mock LLM quickly.
    
    Returns:
        A MockLLM instance with default "Mock response" output.
    """
    return MockLLM()


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    """
    Sample message list for testing.
    
    Provides a standard message list with system and user messages
    that can be used across tests.

    Returns:
        A simple message list with system and user messages.
    """
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def sample_tool_payload() -> dict[str, Any]:
    """
    Sample tool payload for testing.
    
    Provides a standard tool call payload that can be used
    for testing tool/action functionality.

    Returns:
        A simple tool call payload.
    """
    return {
        "operation": "add",
        "a": 5,
        "b": 3,
    }


@pytest.fixture
def sample_llm_response() -> str:
    """
    Sample LLM response text for testing.
    
    Provides a realistic LLM response that includes both prose
    and structured data, useful for testing parsing.
    
    Returns:
        A sample response string.
    """
    return "I'm doing well, thank you for asking! Here is the data: {'status': 'ok', 'value': 42}"


@pytest.fixture
def sample_json_in_prose() -> str:
    """
    Sample LLM response with JSON wrapped in prose.
    
    This simulates a common LLM behavior where structured output
    is wrapped in explanatory text.
    
    Returns:
        A string with JSON embedded in prose.
    """
    return """Sure! Here is the information you requested:

```json
{"name": "Alice", "age": 30, "active": true}
```

Let me know if you need anything else!"""


@pytest.fixture
def sample_list_in_prose() -> str:
    """
    Sample LLM response with a Python list wrapped in prose.
    
    This simulates LLM output where a list is embedded in explanation.
    
    Returns:
        A string with a Python list embedded in prose.
    """
    return """Based on your request, here are the items:

```python
["apple", "banana", "cherry"]
```

These are sorted alphabetically."""


# ============================================================================
# Mock Adapter (Legacy - for backward compatibility)
# ============================================================================


class MockAdapter:
    """
    A mock adapter for testing without API calls.
    
    Note: This is kept for backward compatibility with existing tests.
    For new tests, prefer using MockLLM which matches the new LLM interface.

    Example:
        >>> adapter = MockAdapter(response="Hello!")
        >>> result = adapter.complete(messages)
        >>> assert result["content"] == "Hello!"
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
    """
    Provide a mock adapter for testing.
    
    Note: This is kept for backward compatibility with existing tests.
    For new tests, prefer using mock_llm which matches the new LLM interface.

    Returns:
        A MockAdapter instance.
    """
    return MockAdapter()


@pytest.fixture
def mock_adapter_response() -> dict[str, Any]:
    """
    Mock adapter response for testing.
    
    Note: This is kept for backward compatibility.

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
# Utility Fixtures
# ============================================================================


@pytest.fixture
def temp_file(tmp_path):
    """
    Provide a temporary file path for testing file operations.
    
    The file is automatically cleaned up after the test.
    
    Args:
        tmp_path: pytest's built-in temporary directory fixture.
        
    Returns:
        A Path object pointing to a temporary file.
    """
    return tmp_path / "test_file.pkl"


@pytest.fixture
def temp_json_file(tmp_path):
    """
    Provide a temporary JSON file path for testing.
    
    The file is automatically cleaned up after the test.
    
    Args:
        tmp_path: pytest's built-in temporary directory fixture.
        
    Returns:
        A Path object pointing to a temporary JSON file.
    """
    return tmp_path / "test_file.json"

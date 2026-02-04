"""
Integration tests for the OpenAI adapter.

These tests hit the real OpenAI API and require:
- OPENAI_API_KEY environment variable
- THOUGHTFLOW_INTEGRATION_TESTS=1 environment variable

Run with:
    THOUGHTFLOW_INTEGRATION_TESTS=1 OPENAI_API_KEY=sk-... pytest tests/integration/test_openai_adapter.py -v
"""

from __future__ import annotations

import os

import pytest

# Skip entire module if integration tests are not enabled
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled (set THOUGHTFLOW_INTEGRATION_TESTS=1)",
    ),
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    ),
]


class TestOpenAIAdapterIntegration:
    """Integration tests for OpenAIAdapter."""

    def test_adapter_initialization(self) -> None:
        """OpenAI adapter should initialize with API key from env."""
        from thoughtflow.adapters import OpenAIAdapter

        adapter = OpenAIAdapter()
        assert adapter is not None

    def test_simple_completion(self) -> None:
        """Should complete a simple message.

        Note: This test is a placeholder and will fail until
        OpenAIAdapter.complete() is implemented.
        """
        from thoughtflow.adapters import OpenAIAdapter

        adapter = OpenAIAdapter()
        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]

        # This will raise NotImplementedError until implemented
        with pytest.raises(NotImplementedError):
            adapter.complete(messages)

    def test_with_parameters(self) -> None:
        """Should accept parameters like temperature and max_tokens.

        Note: This test is a placeholder and will fail until
        OpenAIAdapter.complete() is implemented.
        """
        from thoughtflow.adapters import OpenAIAdapter

        adapter = OpenAIAdapter()
        messages = [{"role": "user", "content": "Count to 3."}]
        params = {"temperature": 0, "max_tokens": 50}

        # This will raise NotImplementedError until implemented
        with pytest.raises(NotImplementedError):
            adapter.complete(messages, params)

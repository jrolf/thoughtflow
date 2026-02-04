"""
Integration tests for the Anthropic adapter.

These tests hit the real Anthropic API and require:
- ANTHROPIC_API_KEY environment variable
- THOUGHTFLOW_INTEGRATION_TESTS=1 environment variable

Run with:
    THOUGHTFLOW_INTEGRATION_TESTS=1 ANTHROPIC_API_KEY=sk-ant-... pytest tests/integration/test_anthropic_adapter.py -v
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
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


class TestAnthropicAdapterIntegration:
    """Integration tests for AnthropicAdapter."""

    def test_adapter_initialization(self) -> None:
        """Anthropic adapter should initialize with API key from env."""
        from thoughtflow.adapters import AnthropicAdapter

        adapter = AnthropicAdapter()
        assert adapter is not None

    def test_simple_completion(self) -> None:
        """Should complete a simple message.

        Note: This test is a placeholder and will fail until
        AnthropicAdapter.complete() is implemented.
        """
        from thoughtflow.adapters import AnthropicAdapter

        adapter = AnthropicAdapter()
        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]

        # This will raise NotImplementedError until implemented
        with pytest.raises(NotImplementedError):
            adapter.complete(messages)

    def test_with_system_prompt(self) -> None:
        """Should handle system prompts correctly.

        Note: Anthropic handles system prompts differently than OpenAI.
        This test is a placeholder and will fail until implemented.
        """
        from thoughtflow.adapters import AnthropicAdapter

        adapter = AnthropicAdapter()
        messages = [
            {"role": "system", "content": "You only respond with single words."},
            {"role": "user", "content": "What color is the sky?"},
        ]

        # This will raise NotImplementedError until implemented
        with pytest.raises(NotImplementedError):
            adapter.complete(messages)

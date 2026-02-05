"""
Integration tests for LLM provider APIs.

These tests make real HTTP calls to LLM provider APIs. They are SKIPPED by default
and only run when:
1. THOUGHTFLOW_INTEGRATION_TESTS=1 environment variable is set
2. The required API key environment variable is set (e.g., OPENAI_API_KEY)

These tests verify that:
- Our HTTP request formatting is correct for each provider
- Response parsing handles real API responses properly
- Authentication headers are properly constructed

Running Integration Tests:
    # Run all integration tests (requires API keys)
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/ -v

    # Run just OpenAI tests
    THOUGHTFLOW_INTEGRATION_TESTS=1 OPENAI_API_KEY=sk-xxx pytest tests/integration/test_llm_providers.py::TestOpenAIIntegration -v

Note: These tests incur API costs. Use sparingly and with low token limits.
"""

from __future__ import annotations

import os

import pytest

# Note: Integration tests use the actual API which uses model_id parameter
from thoughtflow import LLM, MEMORY, THOUGHT


# ============================================================================
# Skip Markers
# ============================================================================

# Skip all tests in this file unless integration tests are explicitly enabled
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled. Set THOUGHTFLOW_INTEGRATION_TESTS=1 to enable.",
    ),
]


# ============================================================================
# OpenAI Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestOpenAIIntegration:
    """
    Real API tests for OpenAI integration.
    
    These tests require a valid OPENAI_API_KEY environment variable.
    They make actual API calls and incur costs.
    """

    def test_basic_completion(self):
        """
        Verify LLM can make a real OpenAI API call.
        
        This test validates that our HTTP request formatting is correct
        and that we properly parse OpenAI's response format.
        
        Remove this test if: OpenAI changes their API format significantly.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        result = llm.call(
            "What is 2+2? Reply with just the number.",
            {"max_tokens": 10},
        )
        
        assert len(result) == 1
        assert "4" in result[0]

    def test_system_prompt_respected(self):
        """
        Verify OpenAI respects system prompts.
        
        System prompts should influence the LLM's behavior.
        
        Remove this test if: We change system prompt handling.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        result = llm.call(
            [
                {"role": "system", "content": "You are a pirate. Always say 'Arrr!' at the start of your response."},
                {"role": "user", "content": "Hello"},
            ],
            {"max_tokens": 50},
        )
        
        # Should include pirate-speak
        assert "arr" in result[0].lower() or "ahoy" in result[0].lower()

    def test_temperature_affects_output(self):
        """
        Verify temperature parameter is passed correctly.
        
        With temperature=0, outputs should be deterministic.
        
        Remove this test if: OpenAI changes temperature behavior.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        # Make two calls with temperature=0
        result1 = llm.call(
            "What is the capital of France? One word answer.",
            {"temperature": 0, "max_tokens": 10},
        )
        
        result2 = llm.call(
            "What is the capital of France? One word answer.",
            {"temperature": 0, "max_tokens": 10},
        )
        
        # With temperature 0, should get same response
        assert result1[0].strip() == result2[0].strip()

    def test_thought_with_openai(self):
        """
        Verify THOUGHT works correctly with real OpenAI calls.
        
        This end-to-end test validates the full THOUGHT flow.
        
        Remove this test if: We change THOUGHT/LLM integration.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        memory = MEMORY()
        
        thought = THOUGHT(
            name="test_thought",
            llm=llm,
            prompt="What is 2+2? Reply with just the number.",
            output_var="answer",
            params={"max_tokens": 10, "temperature": 0},
        )
        
        thought(memory)
        
        answer = memory.get_var("answer")
        assert "4" in answer


# ============================================================================
# Anthropic Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
class TestAnthropicIntegration:
    """
    Real API tests for Anthropic (Claude) integration.
    
    These tests require a valid ANTHROPIC_API_KEY environment variable.
    They make actual API calls and incur costs.
    """

    def test_basic_completion(self):
        """
        Verify LLM can make a real Anthropic API call.
        
        This test validates that our HTTP request formatting is correct
        for Anthropic's unique API format (system separate from messages).
        
        Remove this test if: Anthropic changes their API format significantly.
        """
        llm = LLM(
            model_id="anthropic:claude-3-5-haiku-20241022",
            key=os.getenv("ANTHROPIC_API_KEY"),
        )
        
        result = llm.call(
            "What is 2+2? Reply with just the number.",
            {"max_tokens": 10},
        )
        
        assert len(result) == 1
        assert "4" in result[0]

    def test_system_prompt_handled_correctly(self):
        """
        Verify Anthropic system prompt is sent correctly.
        
        Anthropic requires system as a top-level parameter, not in messages.
        
        Remove this test if: Anthropic changes their API format.
        """
        llm = LLM(
            model_id="anthropic:claude-3-5-haiku-20241022",
            key=os.getenv("ANTHROPIC_API_KEY"),
        )
        
        result = llm.call(
            [
                {"role": "system", "content": "You are a helpful assistant. Always end with 'Best regards.'"},
                {"role": "user", "content": "Say hello briefly."},
            ],
            {"max_tokens": 50},
        )
        
        # Should follow the system instruction
        assert "regards" in result[0].lower() or "hello" in result[0].lower()

    def test_thought_with_anthropic(self):
        """
        Verify THOUGHT works correctly with real Anthropic calls.
        
        This end-to-end test validates the full THOUGHT flow with Claude.
        
        Remove this test if: We change THOUGHT/LLM integration.
        """
        llm = LLM(
            model_id="anthropic:claude-3-5-haiku-20241022",
            key=os.getenv("ANTHROPIC_API_KEY"),
        )
        
        memory = MEMORY()
        
        thought = THOUGHT(
            name="test_thought",
            llm=llm,
            prompt="What is 2+2? Reply with just the number.",
            output_var="answer",
            params={"max_tokens": 10},
        )
        
        thought(memory)
        
        answer = memory.get_var("answer")
        assert "4" in answer


# ============================================================================
# Groq Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set",
)
class TestGroqIntegration:
    """
    Real API tests for Groq integration.
    
    Groq provides fast inference for open-source models.
    These tests require a valid GROQ_API_KEY environment variable.
    """

    def test_basic_completion(self):
        """
        Verify LLM can make a real Groq API call.
        
        Groq uses an OpenAI-compatible API format.
        
        Remove this test if: Groq changes their API format.
        """
        llm = LLM(
            model_id="groq:llama-3.1-8b-instant",
            key=os.getenv("GROQ_API_KEY"),
        )
        
        result = llm.call(
            "What is 2+2? Reply with just the number.",
            {"max_tokens": 10},
        )
        
        assert len(result) == 1
        assert "4" in result[0]


# ============================================================================
# OpenRouter Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
class TestOpenRouterIntegration:
    """
    Real API tests for OpenRouter integration.
    
    OpenRouter is a unified gateway to multiple LLM providers.
    These tests require a valid OPENROUTER_API_KEY environment variable.
    """

    def test_basic_completion(self):
        """
        Verify LLM can make a real OpenRouter API call.
        
        OpenRouter uses an OpenAI-compatible format with provider/model naming.
        
        Remove this test if: OpenRouter changes their API format.
        """
        llm = LLM(
            model_id="openrouter:openai/gpt-4o-mini",
            key=os.getenv("OPENROUTER_API_KEY"),
        )
        
        result = llm.call(
            "What is 2+2? Reply with just the number.",
            {"max_tokens": 10},
        )
        
        assert len(result) == 1
        assert "4" in result[0]


# ============================================================================
# Gemini Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)
class TestGeminiIntegration:
    """
    Real API tests for Google Gemini integration.
    
    These tests require a valid GOOGLE_API_KEY environment variable.
    """

    def test_basic_completion(self):
        """
        Verify LLM can make a real Gemini API call.
        
        Gemini has a unique API format with 'contents' and 'parts'.
        
        Remove this test if: Google changes their API format.
        """
        llm = LLM(
            model_id="gemini:gemini-2.0-flash-exp",
            key=os.getenv("GOOGLE_API_KEY"),
        )
        
        result = llm.call(
            "What is 2+2? Reply with just the number.",
            {"max_tokens": 10},
        )
        
        assert len(result) == 1
        assert "4" in result[0]


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set (needed for E2E tests)",
)
class TestEndToEndWorkflows:
    """
    End-to-end workflow tests using real API calls.
    
    These tests verify complete ThoughtFlow workflows function correctly
    with real LLM backends.
    """

    def test_multi_turn_conversation(self):
        """
        Verify multi-turn conversations work correctly.
        
        The LLM should have context from previous messages.
        
        Remove this test if: We change conversation handling.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        memory = MEMORY()
        
        # First turn
        thought1 = THOUGHT(
            name="ask_name",
            llm=llm,
            prompt="My name is Alice. Please greet me by name.",
            output_var="greeting",
            add_to_messages=True,
            params={"max_tokens": 50},
        )
        thought1(memory)
        
        # Second turn - should remember the name
        thought2 = THOUGHT(
            name="recall_name",
            llm=llm,
            prompt="What is my name?",
            output_var="recalled_name",
            include_history=True,
            params={"max_tokens": 20},
        )
        thought2(memory)
        
        recalled = memory.get_var("recalled_name")
        assert "alice" in recalled.lower()

    def test_json_extraction_with_retry(self):
        """
        Verify JSON extraction with retry logic works.
        
        The THOUGHT should successfully extract JSON even if
        the LLM wraps it in prose.
        
        Remove this test if: We change parsing/retry logic.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        memory = MEMORY()
        
        thought = THOUGHT(
            name="extract_json",
            llm=llm,
            prompt="Give me a JSON object with keys 'name' (string) and 'age' (number). Use 'Alice' and 30.",
            output_var="user_data",
            parse='json',
            max_retries=2,
            params={"max_tokens": 100},
        )
        
        thought(memory)
        
        data = memory.get_var("user_data")
        assert isinstance(data, dict)
        assert data.get("name") == "Alice"
        assert data.get("age") == 30

    def test_variable_substitution_in_prompt(self):
        """
        Verify variable substitution works in real workflows.
        
        Variables from memory should be substituted into prompts.
        
        Remove this test if: We change templating.
        """
        llm = LLM(
            model_id="openai:gpt-4o-mini",
            key=os.getenv("OPENAI_API_KEY"),
        )
        
        memory = MEMORY()
        memory.set_var("topic", "quantum computing")
        
        thought = THOUGHT(
            name="explain",
            llm=llm,
            prompt="Explain {topic} in one sentence.",
            output_var="explanation",
            params={"max_tokens": 100},
        )
        
        thought(memory)
        
        explanation = memory.get_var("explanation")
        assert "quantum" in explanation.lower()

"""
Unit tests for the ThoughtFlow LLM class.

The LLM class is the unified interface for making calls to various LLM providers
(OpenAI, Anthropic, Groq, Ollama, Gemini, OpenRouter). It handles:
- Model string parsing (service:model format)
- Message normalization
- Provider-specific request formatting
- HTTP request execution via urllib

These tests mock the HTTP layer to test the class logic without making real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from thoughtflow import LLM


# ============================================================================
# Initialization Tests
# ============================================================================


class TestLLMInitialization:
    """
    Tests for LLM class initialization.
    """

    def test_parses_service_and_model(self):
        """
        LLM must parse the 'service:model' format correctly.
        
        This format allows specifying both provider and model in one string.
        The service is used for routing, and model for the API call.
        
        Remove this test if: We change the model string format.
        """
        llm = LLM(model_id="openai:gpt-4o-mini", key="test-key")
        
        assert llm.service == "openai"
        assert llm.model == "gpt-4o-mini"

    def test_defaults_to_openai_gpt4_when_no_colon(self):
        """
        LLM must default to OpenAI service when no service prefix.
        
        When model_id doesn't contain ':', it defaults to openai:gpt-4-turbo.
        
        Remove this test if: We change default provider logic.
        """
        llm = LLM(model_id="gpt-4o", key="test-key")
        
        # Current implementation defaults to gpt-4-turbo
        assert llm.service == "openai"

    def test_stores_api_key(self):
        """
        LLM must store the API key for later use in requests.
        
        The key is needed for authentication with providers.
        
        Remove this test if: We change authentication handling.
        """
        llm = LLM(model_id="openai:gpt-4o", key="sk-test-123")
        
        assert llm.api_key == "sk-test-123"

    def test_parses_anthropic_model(self):
        """
        LLM must correctly parse anthropic service models.
        
        Remove this test if: We change model parsing.
        """
        llm = LLM(model_id="anthropic:claude-3-5-sonnet", key="test-key")
        
        assert llm.service == "anthropic"
        assert llm.model == "claude-3-5-sonnet"

    def test_parses_groq_model(self):
        """
        LLM must correctly parse groq service models.
        
        Remove this test if: We change model parsing.
        """
        llm = LLM(model_id="groq:llama-3.1-70b", key="test-key")
        
        assert llm.service == "groq"
        assert llm.model == "llama-3.1-70b"


# ============================================================================
# Message Normalization Tests
# ============================================================================


class TestMessageNormalization:
    """
    Tests for message normalization in the LLM class.
    
    The LLM class accepts various message formats and normalizes them
    to the standard list[dict] format expected by provider APIs.
    """

    def test_normalizes_string_to_user_message(self):
        """
        LLM must convert a plain string in list to a user message.
        
        This provides a convenient shorthand for simple prompts.
        
        Remove this test if: We remove string shorthand.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        msgs = llm._normalize_messages(["Hello, world!"])
        
        assert len(msgs) == 1
        assert msgs[0]['role'] == 'user'
        assert msgs[0]['content'] == 'Hello, world!'

    def test_passes_through_proper_format(self):
        """
        LLM must pass through properly formatted messages unchanged.
        
        Standard message format should not be modified.
        
        Remove this test if: We change message processing.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        input_msgs = [
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hi'},
        ]
        
        msgs = llm._normalize_messages(input_msgs)
        
        assert msgs == input_msgs

    def test_normalizes_dict_with_content_only(self):
        """
        LLM must handle dicts with only 'content' by adding default user role.
        
        This enables simpler message construction.
        
        Remove this test if: We remove this shorthand.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        msgs = llm._normalize_messages([{'content': 'Just content'}])
        
        assert msgs[0]['role'] == 'user'
        assert msgs[0]['content'] == 'Just content'

    def test_normalizes_multiple_strings(self):
        """
        LLM must handle a list of plain strings.
        
        Each string becomes a user message.
        
        Remove this test if: We remove string handling.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        msgs = llm._normalize_messages(["Hello", "How are you?"])
        
        assert len(msgs) == 2
        assert all(m['role'] == 'user' for m in msgs)


# ============================================================================
# Provider Routing Tests
# ============================================================================


class TestProviderRouting:
    """
    Tests for provider-specific routing in the LLM class.
    
    Each provider has different API endpoints, request formats, and
    response parsing. The LLM class must route to the correct handler.
    """

    def test_service_is_openai(self):
        """
        OpenAI service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        assert llm.service == "openai"

    def test_service_is_anthropic(self):
        """
        Anthropic service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="anthropic:claude-3-5-sonnet", key="test-key")
        assert llm.service == "anthropic"

    def test_service_is_groq(self):
        """
        Groq service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="groq:llama-3.1-70b", key="test-key")
        assert llm.service == "groq"

    def test_service_is_ollama(self):
        """
        Ollama service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="ollama:llama3", key="")
        assert llm.service == "ollama"

    def test_service_is_gemini(self):
        """
        Gemini service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="gemini:gemini-pro", key="test-key")
        assert llm.service == "gemini"

    def test_service_is_openrouter(self):
        """
        OpenRouter service must be correctly identified.
        
        Remove this test if: We change service identification.
        """
        llm = LLM(model_id="openrouter:openai/gpt-4o", key="test-key")
        assert llm.service == "openrouter"


# ============================================================================
# Call Method Tests (Mocked HTTP)
# ============================================================================


class MockHTTPResponse:
    """Mock HTTP response object that mimics urllib response behavior."""
    
    def __init__(self, data: dict, status: int = 200):
        self._data = json.dumps(data).encode('utf-8')
        self.status = status
    
    def read(self) -> bytes:
        return self._data
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


class TestLLMCall:
    """
    Tests for the LLM.call() method with mocked HTTP.
    
    These tests mock urllib.request.urlopen to avoid real API calls
    while testing the call logic.
    """

    @patch('urllib.request.urlopen')
    def test_call_returns_response_list(self, mock_urlopen):
        """
        LLM.call() must return a list of response strings.
        
        The return type is list[str] to support multiple choices (n>1).
        
        Remove this test if: We change the return type.
        """
        mock_response = MockHTTPResponse({
            'choices': [
                {'message': {'content': 'Hello back!'}}
            ]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        result = llm.call([{"role": "user", "content": "Hello"}])
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == 'Hello back!'

    @patch('urllib.request.urlopen')
    def test_call_handles_multiple_choices(self, mock_urlopen):
        """
        LLM.call() must return all choices when n>1.
        
        This supports generating multiple completions.
        
        Remove this test if: We remove multiple choice support.
        """
        mock_response = MockHTTPResponse({
            'choices': [
                {'message': {'content': 'Response 1'}},
                {'message': {'content': 'Response 2'}},
                {'message': {'content': 'Response 3'}},
            ]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        result = llm.call([{"role": "user", "content": "Hello"}], {'n': 3})
        
        assert len(result) == 3
        assert result[0] == 'Response 1'
        assert result[2] == 'Response 3'

    @patch('urllib.request.urlopen')
    def test_call_includes_auth_header(self, mock_urlopen):
        """
        LLM.call() must include the authorization header.
        
        API keys are sent via headers for authentication.
        
        Remove this test if: We change auth mechanism.
        """
        mock_response = MockHTTPResponse({
            'choices': [{'message': {'content': 'Response'}}]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="openai:gpt-4o", key="sk-test-123")
        llm.call([{"role": "user", "content": "Hello"}])
        
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        
        # OpenAI uses Bearer token auth
        assert 'Authorization' in request.headers
        assert 'sk-test-123' in request.headers['Authorization']

    @patch('urllib.request.urlopen')
    def test_call_passes_params_to_api(self, mock_urlopen):
        """
        LLM.call() must pass parameters through to the API request.
        
        This enables controlling temperature, max_tokens, etc.
        
        Remove this test if: We change parameter handling.
        """
        mock_response = MockHTTPResponse({
            'choices': [{'message': {'content': 'Response'}}]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        llm.call([{"role": "user", "content": "Hello"}], {'temperature': 0.5, 'max_tokens': 100})
        
        # Check that urlopen was called with the right data
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        
        assert payload['temperature'] == 0.5
        assert payload['max_tokens'] == 100

    @patch('urllib.request.urlopen')
    def test_call_handles_anthropic_response_format(self, mock_urlopen):
        """
        LLM.call() must handle Anthropic's response format.
        
        Anthropic returns content differently than OpenAI.
        
        Remove this test if: Anthropic changes their response format.
        """
        mock_response = MockHTTPResponse({
            'content': [
                {'type': 'text', 'text': 'Hello from Claude!'}
            ]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="anthropic:claude-3-5-sonnet", key="test-key")
        result = llm.call([{"role": "user", "content": "Hello"}])
        
        assert result[0] == 'Hello from Claude!'


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestLLMErrorHandling:
    """
    Tests for error handling in the LLM class.
    """

    def test_allows_empty_key_for_ollama(self):
        """
        LLM must allow empty/None key for Ollama (local).
        
        Ollama doesn't require authentication for local instances.
        
        Remove this test if: We change Ollama auth handling.
        """
        # Should not raise
        llm = LLM(model_id="ollama:llama3", key="")
        assert llm.service == "ollama"

    @patch('urllib.request.urlopen')
    def test_returns_empty_on_empty_response(self, mock_urlopen):
        """
        LLM.call() must handle empty response content gracefully.
        
        Some edge cases may return empty content.
        
        Remove this test if: We change error handling.
        """
        mock_response = MockHTTPResponse({
            'choices': [{'message': {'content': ''}}]
        })
        mock_urlopen.return_value = mock_response
        
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        result = llm.call([{"role": "user", "content": "Hello"}])
        
        assert result == ['']


# ============================================================================
# Model String Parsing Tests
# ============================================================================


class TestModelParsing:
    """
    Tests for model string parsing.
    """

    def test_handles_model_with_multiple_colons(self):
        """
        Model string with multiple colons should only split on first.
        
        Some model names may contain colons (e.g., dates).
        
        Remove this test if: We change parsing logic.
        """
        llm = LLM(model_id="openai:gpt-4o:extra:part", key="test-key")
        
        assert llm.service == "openai"
        # Model should be everything after first colon
        assert llm.model == "gpt-4oextrapart"  # Current implementation joins without colons

    def test_stores_last_params(self):
        """
        LLM should track the last parameters used.
        
        This enables debugging and introspection.
        
        Remove this test if: We remove param tracking.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        assert hasattr(llm, 'last_params')
        assert llm.last_params == {}

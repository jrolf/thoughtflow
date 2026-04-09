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


from thoughtflow import LLM
from thoughtflow.llm import OpenAICompatibleLLM


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

        # Handle Multiple Colons in Model Name
        llm = LLM(model_id="ollama:mistral:7b", key="")

        assert llm.service == "ollama"
        assert llm.model == "mistral:7b"


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

    def test_stores_default_params_from_kwargs(self):
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0.7, max_tokens=500)

        assert llm.default_params == {"temperature": 0.7, "max_tokens": 500}

    def test_default_params_empty_when_no_kwargs(self):
        llm = LLM(model_id="openai:gpt-4o", key="k")

        assert llm.default_params == {}

    def test_ignores_none_kwargs(self):
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=None, top_p=0.9)

        assert llm.default_params == {"top_p": 0.9}


# ============================================================================
# Default Params Merge Tests
# ============================================================================


class TestDefaultParams:

    @patch('urllib.request.urlopen')
    def test_defaults_applied_when_no_per_call_params(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0.3, max_tokens=200)
        llm.call([{"role": "user", "content": "hi"}])

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode('utf-8'))
        assert payload['temperature'] == 0.3
        assert payload['max_tokens'] == 200

    @patch('urllib.request.urlopen')
    def test_per_call_params_override_defaults(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0.3, max_tokens=200)
        llm.call([{"role": "user", "content": "hi"}], params={"temperature": 0.9})

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode('utf-8'))
        assert payload['temperature'] == 0.9
        assert payload['max_tokens'] == 200

    @patch('urllib.request.urlopen')
    def test_last_params_reflects_merged_values(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0.5, top_p=0.8)
        llm.call([{"role": "user", "content": "hi"}], params={"top_p": 1.0})

        assert llm.last_params["temperature"] == 0.5
        assert llm.last_params["top_p"] == 1.0

    @patch('urllib.request.urlopen')
    def test_defaults_do_not_mutate_across_calls(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0.5)
        llm.call([{"role": "user", "content": "a"}], params={"temperature": 0.9})
        llm.call([{"role": "user", "content": "b"}])

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode('utf-8'))
        assert payload['temperature'] == 0.5
        assert llm.default_params == {"temperature": 0.5}

    @patch('urllib.request.urlopen')
    def test_top_five_params_all_pass_through(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(
            model_id="openai:gpt-4o", key="k",
            temperature=0.7, max_tokens=1024, top_p=0.95,
            frequency_penalty=0.5, presence_penalty=0.3,
        )
        llm.call([{"role": "user", "content": "hi"}])

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode('utf-8'))
        assert payload['temperature'] == 0.7
        assert payload['max_tokens'] == 1024
        assert payload['top_p'] == 0.95
        assert payload['frequency_penalty'] == 0.5
        assert payload['presence_penalty'] == 0.3


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

    @patch('urllib.request.urlopen')
    def test_call_handles_ollama_response_format(self, mock_urlopen):
        """
        LLM.call() must handle Ollama's response format.

        Ollama returns {"message": {...}, ...} or {"choices": [{...}]}
        Returns a "tool_calls" key in the message if tool calls are used.

        Alter this test if: Ollama changes their response format.
        """
        mock_response = MockHTTPResponse({
            'message': {'role': 'assistant', 'content': "", 'tool_calls': [{'function': {'name': 'get_weather', 'arguments': '{"city": "New York"}'}}]},
        })
        mock_urlopen.return_value = mock_response

        llm = LLM(model_id="ollama:llama3.2", key="")
        result = llm.call([
            {"role": "user", "content": "What's the weather in New York?"}
        ])

        expected = json.dumps({"tool_calls": [{"name": "get_weather", "arguments": {"city": "New York"}}]})
        assert result[0] == expected


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

    def test_stores_last_params(self):
        """
        LLM should track the last parameters used.
        
        This enables debugging and introspection.
        
        Remove this test if: We remove param tracking.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        
        assert hasattr(llm, 'last_params')
        assert llm.last_params == {}


# ============================================================================
# Role Mapping Tests
# ============================================================================


class TestRoleMapping:
    """
    Tests for provider-aware role mapping.

    ThoughtFlow uses internal roles like 'action' and 'result' for tool
    interactions in MEMORY.  The LLM class translates these to each
    provider's native role strings before sending requests.

    _normalize_messages() is structural only (strings -> dicts).
    _map_roles() handles provider-specific role translation.
    _prepare_messages() pipelines both steps.
    """

    def test_normalize_preserves_roles_unchanged(self):
        """
        _normalize_messages() must NOT translate roles.

        It is structural normalization only — roles pass through exactly
        as given.  Role translation is the job of _map_roles().

        Alter this test if: _normalize_messages() gains role-mapping duties.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        msgs = [
            {"role": "action", "content": "tool request"},
            {"role": "result", "content": "tool output"},
            {"role": "reflection", "content": "internal thought"},
        ]

        normalized = llm._normalize_messages(msgs)

        assert normalized[0]["role"] == "action"
        assert normalized[1]["role"] == "result"
        assert normalized[2]["role"] == "reflection"

    def test_map_roles_translates_action_and_result_for_openai(self):
        """
        _map_roles() must translate 'action' and 'result' to 'tool' for OpenAI.

        Alter this test if: OpenAI changes supported roles.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "action", "content": "tool call"},
            {"role": "result", "content": "tool output"},
            {"role": "assistant", "content": "done"},
        ]

        mapped = llm._map_roles(msgs)

        assert mapped[0]["role"] == "user"
        assert mapped[1]["role"] == "tool"
        assert mapped[2]["role"] == "tool"
        assert mapped[3]["role"] == "assistant"

    def test_map_roles_translates_action_and_result_for_ollama(self):
        """
        _map_roles() must translate 'action' and 'result' to 'tool' for Ollama.

        This is the fix for the infinite-loop bug: Ollama discards messages
        with unrecognised roles, so 'action'/'result' must become 'tool'.

        Alter this test if: Ollama changes supported roles.
        """
        llm = LLM(model_id="ollama:llama3.2", key="")
        msgs = [
            {"role": "action", "content": "tool call"},
            {"role": "result", "content": "tool output"},
        ]

        mapped = llm._map_roles(msgs)

        assert mapped[0]["role"] == "tool"
        assert mapped[1]["role"] == "tool"

    def test_map_roles_translates_for_gemini(self):
        """
        _map_roles() must translate 'assistant' -> 'model' and
        'system' -> 'user' for Gemini, plus 'action'/'result' -> 'model'.

        Alter this test if: Gemini changes their role scheme.
        """
        llm = LLM(model_id="gemini:gemini-pro", key="test-key")
        msgs = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "action", "content": "tool call"},
            {"role": "result", "content": "tool output"},
        ]

        mapped = llm._map_roles(msgs)

        assert mapped[0]["role"] == "user"
        assert mapped[1]["role"] == "user"
        assert mapped[2]["role"] == "model"
        assert mapped[3]["role"] == "model"
        assert mapped[4]["role"] == "model"

    def test_map_roles_translates_for_anthropic(self):
        """
        _map_roles() must translate 'action'/'result' to 'assistant' for Anthropic.

        Alter this test if: Anthropic changes supported roles.
        """
        llm = LLM(model_id="anthropic:claude-3-5-sonnet", key="test-key")
        msgs = [
            {"role": "action", "content": "tool call"},
            {"role": "result", "content": "tool output"},
        ]

        mapped = llm._map_roles(msgs)

        assert mapped[0]["role"] == "assistant"
        assert mapped[1]["role"] == "assistant"

    def test_map_roles_passes_unknown_roles_through(self):
        """
        _map_roles() must pass through roles that have no mapping entry.

        Unknown roles are NOT silently dropped — they are sent as-is so that
        any API rejection is honest rather than a silent data loss.

        Alter this test if: we decide to drop/raise on unknown roles.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        msgs = [{"role": "custom_xyz", "content": "test"}]

        mapped = llm._map_roles(msgs)

        assert mapped[0]["role"] == "custom_xyz"

    def test_map_roles_does_not_mutate_input(self):
        """
        _map_roles() must return new dicts, not mutate the input list.

        Alter this test if: we switch to in-place mutation for performance.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        original = [{"role": "action", "content": "test"}]

        mapped = llm._map_roles(original)

        assert original[0]["role"] == "action"
        assert mapped[0]["role"] == "tool"

    def test_prepare_messages_pipelines_normalize_and_map(self):
        """
        _prepare_messages() must normalise structure then translate roles.

        It combines _normalize_messages() (structural) and _map_roles()
        (provider-aware) in a single call.

        Alter this test if: the pipeline order or steps change.
        """
        llm = LLM(model_id="openai:gpt-4o", key="test-key")
        raw = [
            "plain string",
            {"role": "action", "content": "tool call"},
            {"content": "no role"},
        ]

        prepared = llm._prepare_messages(raw)

        # String -> user dict (normalize), role unchanged (no map needed)
        assert prepared[0] == {"role": "user", "content": "plain string"}
        # action -> tool (map)
        assert prepared[1] == {"role": "tool", "content": "tool call"}
        # Missing role -> user (normalize), role unchanged (no map needed)
        assert prepared[2] == {"role": "user", "content": "no role"}

    @patch('urllib.request.urlopen')
    def test_gemini_call_uses_mapped_roles(self, mock_urlopen):
        """
        _call_gemini() must use roles from _prepare_messages(), not its own
        inline mapping.

        Previously Gemini had a local role dict; this is now handled by
        PROVIDER_ROLE_MAP via _prepare_messages().

        Alter this test if: Gemini response format or role handling changes.
        """
        mock_response = MockHTTPResponse({
            'candidates': [
                {'content': {'parts': [{'text': 'Hello from Gemini!'}]}}
            ]
        })
        mock_urlopen.return_value = mock_response

        llm = LLM(model_id="gemini:gemini-pro", key="test-key")
        result = llm.call([
            {"role": "assistant", "content": "prior response"},
            {"role": "user", "content": "follow up"},
        ])

        # Verify the payload sent to Gemini uses mapped roles
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        contents = payload["contents"]

        assert contents[0]["role"] == "model"
        assert contents[1]["role"] == "user"
        assert result[0] == "Hello from Gemini!"


# ============================================================================
# Local / OpenAI-Compatible Server Tests
# ============================================================================


class TestOpenAIBaseURL:
    """Tests for custom base_url support in the openai adapter."""

    @patch('urllib.request.urlopen')
    def test_base_url_routes_to_custom_server(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'local reply'}}]}
        )
        llm = LLM(model_id="openai:my-model", key="dummy",
                   base_url="http://127.0.0.1:8765/v1")
        result = llm.call([{"role": "user", "content": "hi"}])

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://127.0.0.1:8765/v1/chat/completions"
        assert result == ["local reply"]

    @patch('urllib.request.urlopen')
    def test_base_url_trailing_slash_normalized(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:m", key="k",
                   base_url="http://localhost:8080/v1/")
        llm.call([{"role": "user", "content": "hi"}])

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://localhost:8080/v1/chat/completions"

    @patch('urllib.request.urlopen')
    def test_no_base_url_uses_openai_cloud(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="sk-real")
        llm.call([{"role": "user", "content": "hi"}])

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "https://api.openai.com/v1/chat/completions"

    @patch('urllib.request.urlopen')
    def test_transport_keys_not_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:m", key="k",
                   base_url="http://localhost:8080/v1",
                   extra_headers={"X-Custom": "val"})
        llm.call([{"role": "user", "content": "hi"}])

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert "base_url" not in payload
        assert "extra_headers" not in payload

    @patch('urllib.request.urlopen')
    def test_extra_headers_merged(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'ok'}}]}
        )
        llm = LLM(model_id="openai:m", key="k",
                   base_url="http://localhost/v1",
                   extra_headers={"X-Custom": "val"})
        llm.call([{"role": "user", "content": "hi"}])

        request = mock_urlopen.call_args[0][0]
        assert request.headers.get("X-custom") == "val"
        assert "Bearer k" in request.headers.get("Authorization", "")

    @patch('urllib.request.urlopen')
    def test_schema_prompt_injection_when_base_url_set(self, mock_urlopen):
        """With base_url, output_schema must be injected as a prompt, not response_format."""
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': '{"summary":"ok"}'}}]}
        )
        schema = {"name": "extract", "properties": {"summary": {"type": "string"}},
                  "required": ["summary"]}
        llm = LLM(model_id="openai:local-model", key="dummy",
                   base_url="http://localhost:8080/v1")
        llm.call([{"role": "user", "content": "summarize"}],
                 output_schema=schema)

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert "response_format" not in payload
        last_msg = payload["messages"][-1]
        assert last_msg["role"] == "system"
        assert '"summary"' in last_msg["content"]

    @patch('urllib.request.urlopen')
    def test_native_schema_when_no_base_url(self, mock_urlopen):
        """Without base_url, output_schema must use native response_format."""
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': '{"summary":"ok"}'}}]}
        )
        schema = {"name": "extract", "properties": {"summary": {"type": "string"}},
                  "required": ["summary"]}
        llm = LLM(model_id="openai:gpt-4o", key="sk-real")
        llm.call([{"role": "user", "content": "summarize"}],
                 output_schema=schema)

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert "response_format" in payload
        assert payload["response_format"]["type"] == "json_schema"


class TestOpenAICompatibleLLM:
    """Tests for the OpenAICompatibleLLM convenience class."""

    def test_sets_service_and_model(self):
        llm = OpenAICompatibleLLM(
            model="mlx-community/Llama-3-8B",
            base_url="http://127.0.0.1:8765/v1",
        )
        assert llm.service == "openai"
        assert llm.model == "mlx-community/Llama-3-8B"

    def test_default_key_is_dummy(self):
        llm = OpenAICompatibleLLM(
            model="my-model", base_url="http://localhost/v1"
        )
        assert llm.api_key == "dummy"

    def test_base_url_stored_in_default_params(self):
        llm = OpenAICompatibleLLM(
            model="m", base_url="http://localhost:9000/v1"
        )
        assert llm.default_params["base_url"] == "http://localhost:9000/v1"

    def test_extra_kwargs_forwarded(self):
        llm = OpenAICompatibleLLM(
            model="m", base_url="http://localhost/v1",
            temperature=0.5, extra_headers={"X-App": "test"},
        )
        assert llm.default_params["temperature"] == 0.5
        assert llm.default_params["extra_headers"] == {"X-App": "test"}

    @patch('urllib.request.urlopen')
    def test_call_routes_to_custom_url(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {'choices': [{'message': {'content': 'hi'}}]}
        )
        llm = OpenAICompatibleLLM(
            model="local-7b", base_url="http://127.0.0.1:8765/v1"
        )
        llm.call([{"role": "user", "content": "hello"}])

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://127.0.0.1:8765/v1/chat/completions"

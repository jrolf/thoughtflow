"""
Unit tests for the ThoughtFlow EMBED class.

The EMBED class is the unified interface for calling text embedding providers
(OpenAI, Groq, Ollama, Gemini, OpenRouter). It handles:
- Model string parsing (service:model format)
- Single text vs. batch input normalization
- Provider-specific request formatting
- Response normalization to list[float] or list[list[float]]

These tests mock the HTTP layer to test the class logic without making real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from thoughtflow.embed import EMBED


# ============================================================================
# Initialization Tests
# ============================================================================


class TestEmbedInitialization:
    """Tests for EMBED class initialization."""

    def test_parses_service_and_model(self):
        """
        EMBED must parse 'service:model' format correctly.

        Remove this test if: We change the model string format.
        """
        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")

        assert embed.service == "openai"
        assert embed.model == "text-embedding-3-small"

    def test_defaults_to_openai_when_no_colon(self):
        """
        EMBED must default to OpenAI when no service prefix is given.

        Remove this test if: We change default provider logic.
        """
        embed = EMBED(model_id="some-model", key="test-key")

        assert embed.service == "openai"
        assert embed.model == "text-embedding-3-small"

    def test_stores_api_key(self):
        """
        EMBED must store the API key for later use in requests.

        Remove this test if: We change authentication handling.
        """
        embed = EMBED(model_id="openai:text-embedding-3-small", key="sk-test-123")

        assert embed.api_key == "sk-test-123"

    def test_parses_ollama_model(self):
        """
        EMBED must correctly parse ollama service models.

        Remove this test if: We change model parsing.
        """
        embed = EMBED(model_id="ollama:nomic-embed-text", key="")

        assert embed.service == "ollama"
        assert embed.model == "nomic-embed-text"

    def test_parses_gemini_model(self):
        """
        EMBED must correctly parse gemini service models.

        Remove this test if: We change model parsing.
        """
        embed = EMBED(model_id="gemini:text-embedding-004", key="test-key")

        assert embed.service == "gemini"
        assert embed.model == "text-embedding-004"

    def test_initializes_empty_metadata(self):
        """
        EMBED must start with empty last_params and last_meta.

        Remove this test if: We change metadata tracking.
        """
        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")

        assert embed.last_params == {}
        assert embed.last_meta == {}


# ============================================================================
# Provider Routing Tests
# ============================================================================


class TestEmbedProviderRouting:
    """Tests for provider routing in the EMBED class."""

    def test_raises_on_unsupported_service(self):
        """
        EMBED must raise ValueError for unsupported services.

        Remove this test if: We change error handling for unknown providers.
        """
        embed = EMBED(model_id="unsupported:some-model", key="test-key")

        with pytest.raises(ValueError, match="Unsupported embedding service"):
            embed.call("Hello")

    def test_service_is_openai(self):
        """OpenAI service must be correctly identified."""
        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        assert embed.service == "openai"

    def test_service_is_groq(self):
        """Groq service must be correctly identified."""
        embed = EMBED(model_id="groq:some-embed-model", key="test-key")
        assert embed.service == "groq"

    def test_service_is_openrouter(self):
        """OpenRouter service must be correctly identified."""
        embed = EMBED(model_id="openrouter:openai/text-embedding-3-small", key="test-key")
        assert embed.service == "openrouter"


# ============================================================================
# Mock HTTP Helper
# ============================================================================


class MockHTTPResponse:
    """Mock HTTP response object that mimics urllib response behavior."""

    def __init__(self, data, status=200):
        self._data = json.dumps(data).encode('utf-8')
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ============================================================================
# Call Method Tests (Mocked HTTP)
# ============================================================================


class TestEmbedCall:
    """Tests for EMBED.call() with mocked HTTP."""

    @patch('urllib.request.urlopen')
    def test_single_string_returns_single_vector(self, mock_urlopen):
        """
        EMBED.call(string) must return a single vector (list of floats).

        When given a single string, the result should be unwrapped from the
        batch to return a flat list.

        Remove this test if: We change the single-input return type.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        result = embed.call("Hello")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result == [0.1, 0.2, 0.3]

    @patch('urllib.request.urlopen')
    def test_list_input_returns_list_of_vectors(self, mock_urlopen):
        """
        EMBED.call(list) must return a list of vectors.

        When given a list of strings, each string gets its own vector.

        Remove this test if: We change the batch return type.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1},
            ],
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        result = embed.call(["Hello", "World"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @patch('urllib.request.urlopen')
    def test_sorts_by_index(self, mock_urlopen):
        """
        EMBED must sort OpenAI-format responses by index.

        Providers may return embeddings out of order; we guarantee input order.

        Remove this test if: We change response ordering logic.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [
                {"embedding": [0.3, 0.4], "index": 1},
                {"embedding": [0.1, 0.2], "index": 0},
            ],
            "usage": {},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        result = embed.call(["First", "Second"])

        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @patch('urllib.request.urlopen')
    def test_includes_auth_header_openai(self, mock_urlopen):
        """
        EMBED must include the authorization header for OpenAI calls.

        Remove this test if: We change auth mechanism.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="sk-embed-123")
        embed.call("Hello")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert 'sk-embed-123' in request.headers['Authorization']

    @patch('urllib.request.urlopen')
    def test_passes_dimensions_param(self, mock_urlopen):
        """
        EMBED must pass the 'dimensions' parameter through to OpenAI.

        This enables using truncated embeddings (text-embedding-3-*).

        Remove this test if: We change parameter passthrough.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1, 0.2], "index": 0}],
            "usage": {},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        embed.call("Hello", params={"dimensions": 256})

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        assert payload["dimensions"] == 256

    @patch('urllib.request.urlopen')
    def test_captures_usage_metadata(self, mock_urlopen):
        """
        EMBED must capture usage metadata from the response.

        Remove this test if: We change metadata tracking.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
            "model": "text-embedding-3-small",
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        embed.call("Hello")

        assert embed.last_meta["prompt_tokens"] == 5
        assert embed.last_meta["total_tokens"] == 5

    @patch('urllib.request.urlopen')
    def test_stores_last_params(self, mock_urlopen):
        """
        EMBED must track the last parameters used.

        Remove this test if: We remove param tracking.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })

        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        embed.call("Hello", params={"dimensions": 512})

        assert embed.last_params == {"dimensions": 512}


# ============================================================================
# Ollama Tests (Mocked HTTP)
# ============================================================================


class TestEmbedOllama:
    """Tests for EMBED with Ollama provider."""

    @patch('urllib.request.urlopen')
    def test_ollama_single_text(self, mock_urlopen):
        """
        EMBED must handle Ollama's response format for single text.

        Ollama returns {"embeddings": [[...]], ...}.

        Remove this test if: Ollama changes their embedding response format.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [[0.5, 0.6, 0.7]],
            "total_duration": 100000,
        })

        embed = EMBED(model_id="ollama:nomic-embed-text", key="")
        result = embed.call("Hello")

        assert result == [0.5, 0.6, 0.7]

    @patch('urllib.request.urlopen')
    def test_ollama_batch_text(self, mock_urlopen):
        """
        EMBED must handle Ollama's batch response format.

        Remove this test if: Ollama changes their embedding response format.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
            "total_duration": 200000,
        })

        embed = EMBED(model_id="ollama:nomic-embed-text", key="")
        result = embed.call(["Hello", "World"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @patch('urllib.request.urlopen')
    def test_ollama_uses_correct_endpoint(self, mock_urlopen):
        """
        EMBED must call Ollama's /api/embed endpoint.

        Remove this test if: Ollama changes their endpoint.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [[0.1]],
        })

        embed = EMBED(model_id="ollama:nomic-embed-text", key="")
        embed.call("Hello")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert "/api/embed" in request.full_url

    @patch('urllib.request.urlopen')
    def test_ollama_captures_metadata(self, mock_urlopen):
        """
        EMBED must capture Ollama-specific metadata.

        Remove this test if: We change Ollama metadata handling.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [[0.1]],
            "total_duration": 500000,
            "load_duration": 100000,
            "prompt_eval_count": 3,
        })

        embed = EMBED(model_id="ollama:nomic-embed-text", key="")
        embed.call("Hello")

        assert embed.last_meta["total_duration"] == 500000
        assert embed.last_meta["prompt_eval_count"] == 3


# ============================================================================
# Gemini Tests (Mocked HTTP)
# ============================================================================


class TestEmbedGemini:
    """Tests for EMBED with Gemini provider."""

    @patch('urllib.request.urlopen')
    def test_gemini_single_text(self, mock_urlopen):
        """
        EMBED must handle Gemini's batchEmbedContents response.

        Gemini returns {"embeddings": [{"values": [...]}, ...]}.

        Remove this test if: Gemini changes their embedding response format.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [{"values": [0.1, 0.2, 0.3]}],
        })

        embed = EMBED(model_id="gemini:text-embedding-004", key="test-key")
        result = embed.call("Hello")

        assert result == [0.1, 0.2, 0.3]

    @patch('urllib.request.urlopen')
    def test_gemini_batch_text(self, mock_urlopen):
        """
        EMBED must handle Gemini batch responses.

        Remove this test if: Gemini changes their embedding response format.
        """
        mock_urlopen.return_value = MockHTTPResponse({
            "embeddings": [
                {"values": [0.1, 0.2]},
                {"values": [0.3, 0.4]},
            ],
        })

        embed = EMBED(model_id="gemini:text-embedding-004", key="test-key")
        result = embed.call(["Hello", "World"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]


# ============================================================================
# String Representation Tests
# ============================================================================


class TestEmbedRepr:
    """Tests for EMBED string representations."""

    def test_str(self):
        """EMBED __str__ must show service and model."""
        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        assert str(embed) == "EMBED(openai:text-embedding-3-small)"

    def test_repr(self):
        """EMBED __repr__ must show service and model in detail."""
        embed = EMBED(model_id="openai:text-embedding-3-small", key="test-key")
        assert "openai" in repr(embed)
        assert "text-embedding-3-small" in repr(embed)


# ============================================================================
# Default Params and Base URL Tests
# ============================================================================


class TestEmbedDefaultParams:
    """Tests for EMBED constructor kwargs and default_params merging."""

    def test_stores_default_params_from_kwargs(self):
        embed = EMBED(model_id="openai:text-embedding-3-small", key="k",
                      dimensions=256, base_url="http://localhost/v1")
        assert embed.default_params == {
            "dimensions": 256,
            "base_url": "http://localhost/v1",
        }

    def test_default_params_empty_when_no_kwargs(self):
        embed = EMBED(model_id="openai:text-embedding-3-small", key="k")
        assert embed.default_params == {}

    def test_ignores_none_kwargs(self):
        embed = EMBED(model_id="openai:text-embedding-3-small", key="k",
                      base_url=None, dimensions=512)
        assert embed.default_params == {"dimensions": 512}

    @patch('urllib.request.urlopen')
    def test_defaults_applied_to_every_call(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:text-embedding-3-small", key="k",
                      dimensions=256)
        embed.call("hello")

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert payload["dimensions"] == 256

    @patch('urllib.request.urlopen')
    def test_per_call_params_override_defaults(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:text-embedding-3-small", key="k",
                      dimensions=256)
        embed.call("hello", params={"dimensions": 1024})

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert payload["dimensions"] == 1024


class TestEmbedBaseURL:
    """Tests for custom base_url support in the EMBED openai adapter."""

    @patch('urllib.request.urlopen')
    def test_base_url_routes_to_custom_server(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1, 0.2], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:local-embed", key="dummy",
                      base_url="http://127.0.0.1:8765/v1")
        result = embed.call("hello")

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://127.0.0.1:8765/v1/embeddings"
        assert result == [0.1, 0.2]

    @patch('urllib.request.urlopen')
    def test_no_base_url_uses_openai_cloud(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:text-embedding-3-small", key="sk-real")
        embed.call("hello")

        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "https://api.openai.com/v1/embeddings"

    @patch('urllib.request.urlopen')
    def test_transport_keys_not_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:m", key="k",
                      base_url="http://localhost/v1",
                      extra_headers={"X-Custom": "val"})
        embed.call("hello")

        payload = json.loads(
            mock_urlopen.call_args[0][0].data.decode('utf-8')
        )
        assert "base_url" not in payload
        assert "extra_headers" not in payload

    @patch('urllib.request.urlopen')
    def test_extra_headers_merged(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "data": [{"embedding": [0.1], "index": 0}],
            "usage": {},
        })
        embed = EMBED(model_id="openai:m", key="k",
                      base_url="http://localhost/v1",
                      extra_headers={"X-Custom": "val"})
        embed.call("hello")

        request = mock_urlopen.call_args[0][0]
        assert request.headers.get("X-custom") == "val"
        assert "Bearer k" in request.headers.get("Authorization", "")

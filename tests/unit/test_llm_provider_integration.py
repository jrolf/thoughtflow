"""
Unit tests for provider integration plan (v0.2.2).

Covers unified param pipeline, prompt caching, last_error/last_usage,
reasoning-field fallback, and native provider convenience classes.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from thoughtflow import LLM, cached_system, cached_message
from thoughtflow.llm import OpenAICompatibleLLM
from thoughtflow.llm_params import split_call_params, normalize_usage
from thoughtflow.llm_cache import strip_cache_markers, apply_cache_markers
from thoughtflow.providers import GroqLLM, CerebrasLLM, OpenRouterLLM


class MockHTTPResponse:
    """Minimal urllib response mock."""

    def __init__(self, data_dict):
        self._data = json.dumps(data_dict).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestParamPipeline:
    """WP-P18: unified model-param pipeline."""

    def test_split_call_params_removes_transport(self):
        merged = {
            "temperature": 0.5,
            "base_url": "http://localhost/v1",
            "referer": "https://app.com",
            "title": "App",
        }
        wire, transport = split_call_params(merged)
        assert wire == {"temperature": 0.5}
        assert transport["base_url"] == "http://localhost/v1"
        assert transport["referer"] == "https://app.com"

    def test_reserved_keys_not_in_default_params(self):
        seen = []

        def hook(record):
            seen.append(record)

        llm = LLM(
            model_id="openai:gpt-4o",
            key="k",
            request_timeout=30,
            on_usage=hook,
            temperature=0.3,
        )
        assert llm.request_timeout == 30
        assert llm.on_usage is hook
        assert "request_timeout" not in llm.default_params
        assert "on_usage" not in llm.default_params
        assert llm.default_params["temperature"] == 0.3

    @patch("urllib.request.urlopen")
    def test_openrouter_referer_not_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )
        llm = LLM(
            model_id="openrouter:openai/gpt-4o-mini",
            key="k",
            referer="https://myapp.com",
            title="My App",
        )
        llm.call([{"role": "user", "content": "hi"}])

        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "referer" not in payload
        assert "title" not in payload
        req = mock_urlopen.call_args[0][0]
        assert req.headers["Http-referer"] == "https://myapp.com"
        assert req.headers["X-title"] == "My App"

    @patch("urllib.request.urlopen")
    def test_reasoning_effort_passes_through_groq(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )
        llm = LLM(model_id="groq:openai/gpt-oss-20b", key="k", reasoning_effort="low")
        llm.call([{"role": "user", "content": "hi"}])
        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert payload["reasoning_effort"] == "low"


class TestLastErrorAndUsage:
    """WP-P01 / WP-P22: error and usage visibility."""

    @patch("urllib.request.urlopen")
    def test_last_error_on_http_failure(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="u", code=500, msg="err", hdrs={}, fp=MockHTTPResponse({"error": "fail"})
        )
        llm = LLM(model_id="openai:gpt-4o", key="k")
        choices = llm.call([{"role": "user", "content": "hi"}])
        assert llm.last_error is not None
        assert choices == []

    @patch("urllib.request.urlopen")
    def test_last_usage_normalized_with_cache_tokens(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 900},
            },
        })
        llm = LLM(model_id="openai:gpt-4o", key="k")
        llm.call([{"role": "user", "content": "hi"}])
        assert llm.last_error is None
        assert llm.last_usage["cached_tokens"] == 900

    @patch("urllib.request.urlopen")
    def test_on_usage_callback(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })
        records = []
        llm = LLM(model_id="openai:gpt-4o", key="k", on_usage=records.append)
        llm.call([{"role": "user", "content": "hi"}])
        assert len(records) == 1
        assert records[0]["prompt_tokens"] == 10

    def test_normalize_usage_anthropic_cache_fields(self):
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 0,
            }
        }
        record = normalize_usage(response, "anthropic", "claude-3-5-sonnet")
        assert record["cache_read_input_tokens"] == 80


class TestReasoningFieldFallback:
    """WP-P02: content / reasoning fallback."""

    @patch("urllib.request.urlopen")
    def test_openai_compat_uses_reasoning_when_content_empty(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "", "reasoning": "the answer"}}]
        })
        llm = OpenAICompatibleLLM(model="gpt-oss-120b", base_url="https://api.cerebras.ai/v1")
        choices = llm.call([{"role": "user", "content": "hi"}])
        assert choices == ["the answer"]


class TestPromptCaching:
    """WP-P20 / P21 / P23: prompt cache helpers and wire adapters."""

    def test_cached_system_helper(self):
        msg = cached_system("You are a planner.")
        assert msg["role"] == "system"
        assert msg["cache"] is True

    def test_cached_message_helper(self):
        msg = cached_message("user", "hello")
        assert msg["cache"] is True

    def test_strip_cache_markers_for_replay(self):
        msgs = [cached_system("stable"), {"role": "user", "content": "hi"}]
        stripped = strip_cache_markers(msgs)
        assert "cache" not in stripped[0]
        assert stripped[0]["content"] == "stable"

    def test_replay_key_stable_with_and_without_cache_flag(self):
        llm = LLM(model_id="openai:gpt-4o", key="k", temperature=0)
        key_plain, _ = llm._request_signature(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            {"temperature": 0},
            None,
        )
        key_cached, _ = llm._request_signature(
            [cached_system("sys"), {"role": "user", "content": "hi"}],
            {"temperature": 0},
            None,
        )
        assert key_plain == key_cached

    def test_anthropic_cache_block_on_wire(self):
        msgs = apply_cache_markers(
            [{"role": "user", "content": "hello", "cache": True}],
            "anthropic",
        )
        assert msgs[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    @patch("urllib.request.urlopen")
    def test_anthropic_cached_system_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse({
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })
        llm = LLM(model_id="anthropic:claude-3-5-sonnet", key="k")
        llm.call([cached_system("Long stable system prompt."), {"role": "user", "content": "hi"}])
        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        system = payload["system"]
        assert isinstance(system, list)
        assert system[0]["cache_control"] == {"type": "ephemeral"}


class TestNativeProviderClasses:
    """WP-P06 / P07 / P08: convenience subclasses."""

    def test_groq_llm_qwen_sets_reasoning_format(self):
        llm = GroqLLM("qwen/qwen3-32b", key="k")
        assert llm.default_params["reasoning_format"] == "hidden"

    def test_groq_llm_gpt_oss_no_reasoning_format_default(self):
        llm = GroqLLM("openai/gpt-oss-20b", key="k")
        assert "reasoning_format" not in llm.default_params

    def test_groq_strip_think_blocks(self):
        llm = GroqLLM("qwen/qwen3-32b", key="k", strip_think_blocks=True)
        raw = "<think>noise</think>\n{'a': 1}"
        assert llm._strip_think_blocks(raw) == "{'a': 1}"

    def test_cerebras_llm_user_agent_in_transport(self):
        llm = CerebrasLLM("gpt-oss-120b", key="k")
        assert llm.default_params["extra_headers"]["User-Agent"] == "ThoughtFlow/1.0"

    @patch("urllib.request.urlopen")
    def test_cerebras_sends_user_agent_header(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )
        llm = CerebrasLLM("gpt-oss-120b", key="k")
        llm.call([{"role": "user", "content": "hi"}])
        req = mock_urlopen.call_args[0][0]
        assert "User-agent" in req.headers or "User-Agent" in str(req.headers)

    def test_openrouter_llm_default_referer_transport(self):
        llm = OpenRouterLLM("anthropic/claude-3.5-sonnet", key="k")
        assert "referer" in llm.default_params
        assert "title" in llm.default_params

    @patch("urllib.request.urlopen")
    def test_request_timeout_passed_to_urlopen(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k", request_timeout=45)
        llm.call([{"role": "user", "content": "hi"}])
        assert mock_urlopen.call_args[1].get("timeout") == 45


class TestMultimodalPassthrough:
    """WP-P10: list content preserved."""

    def test_normalize_preserves_list_content(self):
        llm = LLM(model_id="openai:gpt-4o", key="k")
        content = [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]
        norm = llm._normalize_messages([{"role": "user", "content": content}])
        assert norm[0]["content"] == content

    @patch("urllib.request.urlopen")
    def test_openai_payload_preserves_list_content(self, mock_urlopen):
        mock_urlopen.return_value = MockHTTPResponse(
            {"choices": [{"message": {"content": "ok"}}]}
        )
        llm = LLM(model_id="openai:gpt-4o", key="k")
        content = [{"type": "text", "text": "see image"}]
        llm.call([{"role": "user", "content": content}])
        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert payload["messages"][0]["content"] == content

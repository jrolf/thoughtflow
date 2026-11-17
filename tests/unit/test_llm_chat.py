"""
Unit tests for LLM.chat, the structured chat completion path (thoughtflow.llm_chat).

A throwaway http.server on 127.0.0.1 plays the provider. No network, no model.
The server records every request body so tests can assert what went on the wire.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from thoughtflow import LLM, MEMORY, ChatError, ReplayLLM, ReplayMissError

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read",
        "description": "Read a file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
}]


def sse(chunks):
    """Encode a list of dicts as an SSE body ending in [DONE]."""
    lines = ["data: " + json.dumps(chunk) + "\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


class Provider:
    """Scripted provider: set .mode before calling; .bodies collects request JSON."""

    def __init__(self):
        self.mode = "json_tool_call"
        self.bodies = []
        self.server = None
        self.release = threading.Event()

    def start(self):
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                provider.bodies.append(body)
                provider.reply(self, body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return "http://127.0.0.1:{}/v1".format(self.server.server_address[1])

    def stop(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()

    def send_json(self, handler, status, payload):
        data = json.dumps(payload).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def reply(self, handler, body):
        mode = self.mode
        if mode == "json_tool_call":
            self.send_json(handler, 200, {
                "model": "m1",
                "choices": [{"finish_reason": "tool_calls", "message": {
                    "role": "assistant", "content": None, "reasoning": "thinking it over",
                    "tool_calls": [{"id": "call_9", "type": "function",
                                    "function": {"name": "read", "arguments": "{\"path\": \"a.py\"}"}}],
                }}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7, "cost": 0.0004},
            })
        elif mode == "json_bad_args":
            self.send_json(handler, 200, {"choices": [{"finish_reason": "tool_calls", "message": {
                "tool_calls": [{"id": "c", "function": {"name": "read", "arguments": "{\"path\": "}}]}}]})
        elif mode == "http_429":
            self.send_json(handler, 429, {"error": "slow down"})
        elif mode == "http_400":
            self.send_json(handler, 400, {"error": "bad request"})
        elif mode == "sse":
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            handler.wfile.write(b": keep-alive comment\n\n")
            handler.wfile.write(sse([
                {"model": "m1", "choices": [{"delta": {"reasoning_content": "hm "}}]},
                {"choices": [{"delta": {"content": "Hel"}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "re", "arguments": ""}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "ad", "arguments": "{\"pa"}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "th\": \"x\"}"}}]}}]},
                {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 3}},
            ]))
        elif mode == "sse_stall":
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            handler.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "part"}}]}) + "\n\n").encode())
            handler.wfile.flush()
            self.release.wait(10)
        elif mode == "stall_headers":
            self.release.wait(10)
        elif mode == "sse_error":
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            handler.wfile.write(sse([{"error": {"message": "upstream exploded"}}]))


@pytest.fixture
def provider():
    scripted = Provider()
    scripted.base_url = scripted.start()
    yield scripted
    scripted.stop()


def make_llm(provider, **kwargs):
    return LLM("openai:test-model", key="k", base_url=provider.base_url, **kwargs)


class TestNonStreaming:
    def test_returns_full_message_with_native_tool_call(self, provider):
        message = make_llm(provider).chat([{"role": "user", "content": "go"}], tools=TOOLS)
        assert message["content"] == ""
        assert message["reasoning"] == "thinking it over"
        assert message["finish_reason"] == "tool_calls"
        assert message["tool_calls"][0]["name"] == "read"
        assert message["tool_calls"][0]["arguments"] == {"path": "a.py"}
        assert message["tool_calls"][0]["arguments_error"] is None
        assert message["usage"]["prompt_tokens"] == 12
        assert message["usage"]["cost"] == 0.0004
        assert message["model"] == "m1"

    def test_tools_and_tool_messages_go_on_the_wire_verbatim(self, provider):
        history = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "file text"},
        ]
        make_llm(provider, max_tokens=50).chat(history, tools=TOOLS)
        body = provider.bodies[0]
        assert body["messages"] == history
        assert body["tools"] == TOOLS
        assert body["max_tokens"] == 50
        assert "stream" not in body
        assert "base_url" not in body

    def test_invalid_arguments_are_reported_not_repaired(self, provider):
        provider.mode = "json_bad_args"
        message = make_llm(provider).chat([{"role": "user", "content": "go"}])
        call = message["tool_calls"][0]
        assert call["arguments"] == {}
        assert call["raw_arguments"] == "{\"path\": "
        assert "not valid JSON" in call["arguments_error"]

    def test_http_errors_carry_retryability(self, provider):
        provider.mode = "http_429"
        with pytest.raises(ChatError) as caught:
            make_llm(provider).chat([{"role": "user", "content": "go"}])
        assert caught.value.status == 429 and caught.value.retryable is True
        provider.mode = "http_400"
        with pytest.raises(ChatError) as caught:
            make_llm(provider).chat([{"role": "user", "content": "go"}])
        assert caught.value.status == 400 and caught.value.retryable is False

    def test_unsupported_service_is_refused(self):
        with pytest.raises(ValueError):
            LLM("anthropic:claude", key="k").chat([{"role": "user", "content": "x"}])

    def test_last_usage_and_on_usage_are_updated(self, provider):
        seen = []
        llm = make_llm(provider, on_usage=seen.append)
        llm.chat([{"role": "user", "content": "go"}])
        assert llm.last_usage["completion_tokens"] == 7
        assert len(seen) == 1

    def test_abort_while_waiting_for_headers(self, provider):
        provider.mode = "stall_headers"
        cancel = threading.Event()
        threading.Timer(0.2, cancel.set).start()
        started = time.time()
        message = make_llm(provider).chat([{"role": "user", "content": "go"}], cancel=cancel)
        assert message["finish_reason"] == "aborted"
        assert time.time() - started < 3


class TestStreaming:
    def test_events_and_final_message(self, provider):
        provider.mode = "sse"
        events = list(make_llm(provider).chat([{"role": "user", "content": "go"}], tools=TOOLS, stream=True))
        kinds = [event["type"] for event in events]
        assert kinds[-1] == "done"
        assert "".join(e["delta"] for e in events if e["type"] == "text_delta") == "Hello"
        assert [e["delta"] for e in events if e["type"] == "reasoning_delta"] == ["hm "]
        message = events[-1]["message"]
        assert message["content"] == "Hello"
        assert message["reasoning"] == "hm "
        assert message["tool_calls"][0]["name"] == "read"
        assert message["tool_calls"][0]["arguments"] == {"path": "x"}
        assert message["finish_reason"] == "tool_calls"
        assert message["usage"]["prompt_tokens"] == 5
        assert provider.bodies[0]["stream"] is True
        assert provider.bodies[0]["stream_options"] == {"include_usage": True}

    def test_abort_mid_stream_returns_partial_message(self, provider):
        provider.mode = "sse_stall"
        cancel = threading.Event()
        stream = make_llm(provider).chat([{"role": "user", "content": "go"}], stream=True, cancel=cancel)
        first = next(stream)
        assert first == {"type": "text_delta", "delta": "part"}
        started = time.time()
        threading.Timer(0.1, cancel.set).start()
        rest = list(stream)
        assert rest[-1]["type"] == "done"
        assert rest[-1]["message"]["finish_reason"] == "aborted"
        assert rest[-1]["message"]["content"] == "part"
        assert time.time() - started < 3

    def test_mid_stream_provider_error_raises(self, provider):
        provider.mode = "sse_error"
        with pytest.raises(ChatError) as caught:
            list(make_llm(provider).chat([{"role": "user", "content": "go"}], stream=True))
        assert "upstream exploded" in str(caught.value)


class TestRecordReplay:
    def test_recorded_chat_replays_for_both_modes(self, provider):
        history = [{"role": "user", "content": "go"}]
        memory = MEMORY()
        live = make_llm(provider).record(memory)
        recorded = live.chat(history, tools=TOOLS)

        replay = ReplayLLM(memory)
        assert replay.chat(history, tools=TOOLS) == recorded
        events = list(replay.chat(history, tools=TOOLS, stream=True))
        assert events[-1]["type"] == "done"
        assert events[-1]["message"] == recorded
        assert any(e["type"] == "tool_call_delta" for e in events)

    def test_replay_miss_fails_loudly(self, provider):
        memory = MEMORY()
        make_llm(provider).record(memory).chat([{"role": "user", "content": "a"}])
        with pytest.raises(ReplayMissError):
            ReplayLLM(memory).chat([{"role": "user", "content": "different"}])

    def test_recorded_streams_are_recorded_too(self, provider):
        provider.mode = "sse"
        memory = MEMORY()
        history = [{"role": "user", "content": "go"}]
        list(make_llm(provider).record(memory).chat(history, stream=True))
        message = ReplayLLM(memory).chat(history)
        assert message["content"] == "Hello"

"""
Structured chat completions for ThoughtFlow's LLM (``LLM.chat``).

WHY THIS MODULE EXISTS
----------------------
``LLM.call`` returns a list of strings. That is the right shape for THOUGHT and
the other text primitives, but it throws away everything an agent loop needs:
native ``tool_calls``, the reasoning text kept apart from the answer, the
``finish_reason`` and the token usage. ``LLM.chat`` is the structured twin of
``call``: it takes OpenAI-format messages (including assistant ``tool_calls``
and ``tool`` results, passed through verbatim) and an optional ``tools`` list,
and returns the whole assistant message as one plain dict.

THE RESULT SHAPE (plain dict)
-----------------------------
    {
        "role": "assistant",
        "content": "the answer text, possibly empty",
        "reasoning": "reasoning text, kept separate from content",
        "tool_calls": [
            {"id": "call_1", "name": "read", "arguments": {"path": "a.py"},
             "raw_arguments": "{\\"path\\": \\"a.py\\"}", "arguments_error": None},
        ],
        "finish_reason": "stop" | "tool_calls" | "length" | "aborted" | ...,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, ...} or None,
        "model": "model name echoed by the server",
    }

A tool call whose arguments are not valid JSON keeps ``arguments`` as ``{}``,
keeps the raw text in ``raw_arguments``, and sets ``arguments_error``. The
caller decides what to do (an agent loop turns it into an error tool result
the model can see and retry). It is never silently repaired here.

STREAMING
---------
``chat(..., stream=True)`` returns a generator of event dicts:

    {"type": "text_delta", "delta": "..."}
    {"type": "reasoning_delta", "delta": "..."}
    {"type": "tool_call_delta", "index": 0, "id": "call_1", "name": "read",
     "arguments_delta": "{\\"pa"}
    {"type": "done", "message": {... the result shape above ...}}

The last event is always ``done``. Errors raise ``ChatError`` from the
generator. Pass ``cancel=threading.Event()`` to abort from another thread: the
socket is shut down immediately (even while waiting for the first byte of a long
prompt-processing delay), and the stream ends with a ``done`` event whose
``finish_reason`` is ``"aborted"`` and whose message holds whatever arrived.

SCOPE
-----
Services that speak the OpenAI chat-completions dialect: ``openai`` (including
any ``base_url`` such as a local MLX server), ``openrouter``, and ``groq``.
Anthropic, Gemini and Ollama are not supported by ``chat`` yet. HTTP goes
through ``http.client`` (not ``urllib``) so a socket is in hand for abort; as a
consequence environment proxy variables are not honored.

Nothing here prints. Library code that writes to stdout breaks hosts that use
stdout as a protocol channel (RPC mode), so failures are exceptions, not prints.
"""

from __future__ import annotations

import http.client
import json
import socket
import threading
import urllib.parse

from thoughtflow.llm_params import normalize_usage

# Services whose request and response shapes this module understands.
CHAT_SERVICES = frozenset({"openai", "openrouter", "groq"})

# HTTP statuses worth retrying: timeouts, conflicts, rate limits, and any server error.
RETRYABLE_STATUSES = frozenset({408, 409, 425, 429})


class ChatError(Exception):
    """
    A failed chat request.

    Attributes:
        status (int or None): HTTP status when the failure was an HTTP error.
        body (str): Response body text (truncated), when there was one.
        retryable (bool): True for rate limits, server errors, and network
            failures; False for client errors such as a bad request.
    """

    def __init__(self, message, status=None, body="", retryable=False):
        super().__init__(message)
        self.status = status
        self.body = body
        self.retryable = retryable


def chat_endpoint(service, api_key, transport):
    """
    Return ``(url, headers)`` for an OpenAI-compatible chat-completions call.

    Args:
        service (str): ``openai``, ``openrouter`` or ``groq``.
        api_key (str): Bearer token.
        transport (dict): Transport params split out of the call params
            (``base_url``, ``extra_headers``, ``referer``, ``title``).

    Raises:
        ValueError: For a service this module does not support.
    """
    transport = transport or {}
    headers = {
        "Authorization": "Bearer " + str(api_key),
        "Content-Type": "application/json",
    }
    if service == "openai":
        base_url = transport.get("base_url") or "https://api.openai.com/v1"
        url = base_url.rstrip("/") + "/chat/completions"
    elif service == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers["HTTP-Referer"] = transport.get("referer", "https://your-app.com")
        headers["X-Title"] = transport.get("title", "ThoughtFlow")
    elif service == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers["User-Agent"] = "Groq/Python 0.9.0"
    else:
        raise ValueError(
            "LLM.chat supports the openai, openrouter and groq services, not '{}'.".format(service)
        )
    extra_headers = transport.get("extra_headers")
    if extra_headers:
        headers.update(extra_headers)
    return url, headers


def build_chat_payload(model, messages, tools, wire_params, stream):
    """
    Build the JSON request body.

    Messages and tools go through verbatim. For streaming, ``stream_options``
    asks the server to append a final usage chunk, unless the caller already
    set it in ``wire_params``.
    """
    payload = {"model": model, "messages": messages}
    payload.update(wire_params)
    if tools:
        payload["tools"] = tools
    if stream:
        payload["stream"] = True
        payload.setdefault("stream_options", {"include_usage": True})
    return payload


def shutdown_connection(connection):
    """
    Shut the socket down so a thread blocked in recv wakes up, then close.

    ``http.client`` sets ``connection.sock`` to None once a response is known to
    close the connection (every HTTP/1.0 style reply), but the response keeps
    reading from the same socket. ``open_chat_request`` therefore saves the socket
    as ``connection.tf_sock`` right after connecting, and that is what we shut down.
    """
    sock = getattr(connection, "tf_sock", None) or connection.sock
    try:
        if sock is not None:
            sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        connection.close()
    except OSError:
        pass


def _watch_cancel(cancel, connection, finished):
    """Background watcher: when ``cancel`` is set, abort the connection."""
    while not finished.is_set():
        if cancel.wait(0.05):
            if not finished.is_set():
                shutdown_connection(connection)
            return


def open_chat_request(url, headers, body, timeout, cancel):
    """
    Open the HTTP request and return ``(connection, response, finished)``.

    ``finished`` is an Event the caller sets when done with the response, which
    lets the cancel watcher thread exit. The watcher exists only when ``cancel``
    is given. Raises ``ChatError`` for HTTP errors and network failures, and
    marks an abort (cancel set while connecting or waiting for headers) with a
    ``ChatError`` whose ``status`` is ``"aborted"``.
    """
    parts = urllib.parse.urlsplit(url)
    connection_class = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parts.netloc, timeout=timeout)
    finished = threading.Event()
    path = parts.path + ("?" + parts.query if parts.query else "")
    try:
        connection.connect()
        connection.tf_sock = connection.sock
        if cancel is not None:
            watcher = threading.Thread(target=_watch_cancel, args=(cancel, connection, finished), daemon=True)
            watcher.start()
        connection.request("POST", path, body, headers)
        response = connection.getresponse()
    except (OSError, http.client.HTTPException) as exc:
        finished.set()
        shutdown_connection(connection)
        if cancel is not None and cancel.is_set():
            raise ChatError("aborted", status="aborted")
        raise ChatError("Network error: {}".format(exc), retryable=True)

    if response.status >= 400:
        body_text = response.read().decode("utf-8", errors="replace")[:2000]
        finished.set()
        shutdown_connection(connection)
        retryable = response.status in RETRYABLE_STATUSES or response.status >= 500
        raise ChatError(
            "HTTP {}: {}".format(response.status, body_text[:300]),
            status=response.status, body=body_text, retryable=retryable,
        )
    return connection, response, finished


def parse_tool_calls(raw_tool_calls):
    """
    Normalize provider ``tool_calls`` into the result shape.

    Args:
        raw_tool_calls (list): The ``tool_calls`` list of an OpenAI-format
            message: ``{"id", "type", "function": {"name", "arguments"}}``,
            where ``arguments`` is normally a JSON string.

    Returns:
        list[dict]: ``{"id", "name", "arguments", "raw_arguments", "arguments_error"}``.
    """
    calls = []
    for position, raw in enumerate(raw_tool_calls or []):
        function = raw.get("function") or {}
        raw_arguments = function.get("arguments", "")
        arguments = {}
        error = None
        if isinstance(raw_arguments, dict):
            arguments = raw_arguments
            raw_arguments = json.dumps(raw_arguments)
        elif str(raw_arguments).strip():
            try:
                parsed = json.loads(raw_arguments)
            except ValueError as exc:
                parsed = None
                error = "Arguments are not valid JSON: {}".format(exc)
            if parsed is not None and not isinstance(parsed, dict):
                error = "Arguments must be a JSON object, got {}".format(type(parsed).__name__)
            elif parsed is not None:
                arguments = parsed
        calls.append({
            "id": raw.get("id") or "call_{}".format(position),
            "name": function.get("name", ""),
            "arguments": arguments,
            "raw_arguments": raw_arguments,
            "arguments_error": error,
        })
    return calls


def normalize_chat_usage(service, model, raw_usage):
    """Normalize a raw usage block, keeping the provider-reported ``cost`` when present."""
    if not raw_usage:
        return None
    usage = normalize_usage({"usage": raw_usage}, service, model) or {}
    if raw_usage.get("cost") is not None:
        usage["cost"] = raw_usage["cost"]
    return usage


def build_message(service, model, content, reasoning, tool_calls, finish_reason, raw_usage, echoed_model=None):
    """Assemble the result-shape dict from its parts."""
    return {
        "role": "assistant",
        "content": content,
        "reasoning": reasoning,
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
        "usage": normalize_chat_usage(service, model, raw_usage),
        "model": echoed_model or model,
    }


def message_reasoning(message):
    """Reasoning text from a provider message (``reasoning`` or ``reasoning_content``)."""
    return message.get("reasoning") or message.get("reasoning_content") or ""


def read_chat_response(service, model, response):
    """Parse a complete (non-streaming) response body into the result shape."""
    text = response.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        raise ChatError("Non-JSON response: {}".format(text[:200]), body=text[:2000])
    if isinstance(parsed, dict) and parsed.get("error"):
        raise ChatError("Provider error: {}".format(str(parsed["error"])[:300]), body=text[:2000], retryable=True)
    choices = parsed.get("choices") or []
    if not choices:
        raise ChatError("Response had no choices: {}".format(text[:200]), body=text[:2000])
    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)
    return build_message(
        service, model, content, message_reasoning(message),
        parse_tool_calls(message.get("tool_calls")), choice.get("finish_reason"),
        parsed.get("usage"), parsed.get("model"),
    )


def new_stream_state():
    """Fresh accumulator for a streamed response (plain dict)."""
    return {
        "content": [], "reasoning": [], "tool_calls": {}, "finish_reason": None,
        "usage": None, "model": None,
    }


def feed_stream_chunk(state, chunk):
    """
    Fold one parsed SSE chunk into ``state`` and return the events it produced.

    Raises:
        ChatError: When the chunk carries a provider error (OpenRouter and
            others report mid-stream failures this way).
    """
    events = []
    if chunk.get("error"):
        raise ChatError("Provider error: {}".format(str(chunk["error"])[:300]), retryable=True)
    if chunk.get("model"):
        state["model"] = chunk["model"]
    if chunk.get("usage"):
        state["usage"] = chunk["usage"]
    for choice in chunk.get("choices") or []:
        delta = choice.get("delta") or {}
        text = delta.get("content")
        if text:
            state["content"].append(text)
            events.append({"type": "text_delta", "delta": text})
        thinking = delta.get("reasoning") or delta.get("reasoning_content")
        if thinking:
            state["reasoning"].append(thinking)
            events.append({"type": "reasoning_delta", "delta": thinking})
        for raw in delta.get("tool_calls") or []:
            index = raw.get("index", 0)
            slot = state["tool_calls"].setdefault(index, {"id": None, "name": "", "arguments": ""})
            function = raw.get("function") or {}
            if raw.get("id"):
                slot["id"] = raw["id"]
            if function.get("name"):
                slot["name"] += function["name"]
            piece = function.get("arguments") or ""
            slot["arguments"] += piece
            events.append({
                "type": "tool_call_delta", "index": index, "id": slot["id"],
                "name": slot["name"], "arguments_delta": piece,
            })
        if choice.get("finish_reason"):
            state["finish_reason"] = choice["finish_reason"]
    return events


def finish_stream_state(service, model, state, aborted=False):
    """Turn a stream accumulator into the result-shape message."""
    raw_calls = []
    for index in sorted(state["tool_calls"]):
        slot = state["tool_calls"][index]
        raw_calls.append({
            "id": slot["id"],
            "function": {"name": slot["name"], "arguments": slot["arguments"]},
        })
    finish_reason = "aborted" if aborted else state["finish_reason"]
    return build_message(
        service, model, "".join(state["content"]), "".join(state["reasoning"]),
        parse_tool_calls(raw_calls), finish_reason, state["usage"], state["model"],
    )


def iter_stream_chunks(response):
    """Yield parsed JSON chunks from an SSE response, stopping at ``[DONE]``."""
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        # Blank lines separate events; lines starting with ':' are SSE comments
        # (OpenRouter sends ': OPENROUTER PROCESSING' keep-alives).
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if line == "[DONE]":
            return
        try:
            yield json.loads(line)
        except ValueError:
            continue


def message_to_events(message):
    """
    Replay a finished message as the events a live stream would have produced.

    Used by ReplayLLM so streaming consumers work unchanged against recordings.
    """
    events = []
    if message.get("reasoning"):
        events.append({"type": "reasoning_delta", "delta": message["reasoning"]})
    if message.get("content"):
        events.append({"type": "text_delta", "delta": message["content"]})
    for index, call in enumerate(message.get("tool_calls") or []):
        events.append({
            "type": "tool_call_delta", "index": index, "id": call["id"],
            "name": call["name"], "arguments_delta": call.get("raw_arguments", ""),
        })
    events.append({"type": "done", "message": message})
    return events

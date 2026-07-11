"""
LLM class for ThoughtFlow.

A unified interface for calling various language model services.

Unified param pipeline (v0.2.2+):
  - Constructor kwargs split into reserved (request_timeout, on_usage, record),
    transport (base_url, referer, extra_headers), and model (temperature, etc.).
  - split_call_params() ensures transport keys never leak into JSON bodies.
  - Prompt caching via cache=True on messages or cached_system() helpers.

Also home to ThoughtFlow's record/replay system: LLM.record(memory) captures
every exchange as MEMORY events, and LLM.replay(memory) returns a ReplayLLM
that serves those recorded responses deterministically — offline, instant,
and byte-identical. Because MEMORY is event-sourced, no separate session or
trace machinery is needed: the memory IS the recording.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error

from thoughtflow._util import exchange_key, TRANSPORT_PARAM_KEYS
from thoughtflow.llm_params import (
    LLM_RESERVED_KEYS,
    merge_call_params,
    split_call_params,
    normalize_usage,
    build_gemini_generation_config,
    pick_anthropic_wire_params,
)
from thoughtflow.llm_cache import (
    apply_cache_markers,
    strip_cache_markers,
    format_anthropic_system,
)


class ReplayMissError(KeyError):
    """Raised when a ReplayLLM receives a request that was never recorded."""


# Maps ThoughtFlow-internal roles to each provider's accepted role strings.
# Only non-identity mappings are listed; roles not present here pass through
# unchanged.  This is pure configuration — behaviour lives in _map_roles().
PROVIDER_ROLE_MAP = {
    "openai":     {"action": "tool",      "result": "tool"},
    "groq":       {"action": "tool",      "result": "tool"},
    "anthropic":  {"action": "assistant", "result": "assistant"},
    "ollama":     {"action": "tool",      "result": "tool"},
    "gemini":     {"action": "model",     "result": "model",
                   "assistant": "model",  "system": "user"},
    "openrouter": {"action": "tool",      "result": "tool"},
}


class LLM:
    """
    The LLM class is designed to interface with various language model services.
    
    Attributes:
        service (str): The name of the service provider (e.g., 'openai', 'groq', 'anthropic').
        model (str): The specific model to be used within the service.
        api_key (str): The API key for authenticating requests.
        api_secret (str): The API secret for additional authentication.
        default_params (dict): Default parameters applied to every call (set via constructor kwargs).
        last_params (dict): Stores the merged parameters used in the last API call.

    Methods:
        __init__(model_id, key, secret, **kwargs):
            Initializes the LLM instance. Any additional keyword arguments
            (temperature, max_tokens, top_p, frequency_penalty, presence_penalty,
            etc.) are stored as defaults applied to every call.  Per-call params
            override these defaults.
        
        call(msg_list, params):
            Calls the appropriate API based on the service with the given message list and parameters.
        
        _normalize_messages(msg_list):
            Structural normalization only — coerces inputs into message dicts
            without changing roles.
        
        _map_roles(msg_list):
            Translates ThoughtFlow-internal roles (e.g. 'action', 'result')
            to provider-native role strings using PROVIDER_ROLE_MAP.
        
        _prepare_messages(msg_list):
            Convenience pipeline: _normalize_messages() then _map_roles().
            All _call_* methods use this.
        
        _call_openai(msg_list, params):
            Sends a request to the OpenAI API with the specified messages and parameters.
        
        _call_groq(msg_list, params):
            Sends a request to the Groq API with the specified messages and parameters.
        
        _call_anthropic(msg_list, params):
            Sends a request to the Anthropic API with the specified messages and parameters.

        _call_ollama(msg_list, params):
            Sends a request to the Ollama API with the specified messages and parameters.
        
        _send_request(url, data, headers):
            Helper function to send HTTP requests to the specified URL with data and headers.
    """
    def __init__(self, model_id='', key='API_KEY', secret='API_SECRET', **kwargs):
        # Parse model ID and initialize service and model name
        if ':' not in model_id: model_id = 'openai:gpt-4-turbo'
        
        service, model = model_id.split(':', 1)
        self.service = service
        self.model = model
        self.api_key = key
        self.api_secret = secret
        self.last_params = {}
        self.default_params = {}
        self.last_error = None
        self.last_usage = None
        self.request_timeout = None
        self.on_usage = None

        # Reserved client keys — never stored in default_params or sent on wire
        self._record_memory = kwargs.pop('record', None)
        if 'request_timeout' in kwargs:
            self.request_timeout = kwargs.pop('request_timeout')
        if 'on_usage' in kwargs:
            self.on_usage = kwargs.pop('on_usage')

        # Model + transport kwargs (transport split out at call time via split_call_params)
        for k, v in kwargs.items():
            if k in LLM_RESERVED_KEYS:
                continue
            if v is not None:
                self.default_params[k] = v

        # Make the object directly callable
        self.__call__ = self.call

    def record(self, memory):
        """
        Start recording every exchange into the given MEMORY.

        Each subsequent call() appends an exchange event (request + response,
        keyed by content hash) to the memory. Save the memory and use
        LLM.replay() to re-run the flow deterministically without the network.

        Args:
            memory: A MEMORY instance, or None to stop recording.

        Returns:
            self (for chaining: ``llm = LLM(...).record(memory)``).
        """
        self._record_memory = memory
        return self

    def _request_signature(self, msg_list, params, output_schema):
        """Build the canonical (key, request) pair for an exchange.

        Messages are structurally normalized but NOT provider-role-mapped,
        and transport-only params are excluded — so the key depends purely
        on logical content and survives endpoint changes.
        """
        clean_params = {
            k: v for k, v in params.items() if k not in TRANSPORT_PARAM_KEYS
        }
        request = {
            'messages': strip_cache_markers(self._normalize_messages(msg_list)),
            'params': clean_params,
            'output_schema': output_schema,
        }
        key = exchange_key(self.service, self.model, request)
        return key, request

    def _record_exchange(self, key, request, choices):
        """Append one exchange event to the recording memory (if any)."""
        if self._record_memory is None:
            return
        self._record_memory.add_exchange(
            kind='chat',
            key=key,
            service=self.service,
            model=self.model,
            request=request,
            response=list(choices),
        )

    def _record_stream(self, gen, key, request):
        """Wrap a streaming generator so the joined text is recorded on completion."""
        chunks = []
        for chunk in gen:
            chunks.append(chunk)
            yield chunk
        self._record_exchange(key, request, ["".join(chunks)])

    @classmethod
    def replay(cls, memory, on_miss='raise', model_id=None):
        """
        Build a ReplayLLM that serves responses recorded in the given MEMORY.

        The returned object is call-compatible with LLM, so it can be handed
        to any THOUGHT, AGENT, or WORKFLOW in place of a live model. Requests
        are matched by content hash; flows replay deterministically, offline,
        with no API keys.

        Args:
            memory: A MEMORY containing recorded exchanges (see LLM.record).
            on_miss: 'raise' (default) to fail loudly on an unrecorded
                request, or a live LLM instance to fall back to.
            model_id: 'service:model' to replay as. Only needed when the
                memory contains recordings from more than one model.

        Returns:
            ReplayLLM

        Example:
            >>> recorded = MEMORY.from_json('session.json')
            >>> llm = LLM.replay(recorded)
            >>> memory = my_flow(MEMORY(), llm)   # deterministic, offline
        """
        return ReplayLLM(memory, on_miss=on_miss, model_id=model_id)

    def _normalize_messages(self, msg_list):
        """
        Structural normalization only — coerces inputs into message dicts.

        Roles are passed through exactly as provided; no provider-specific
        translation happens here.  Use _prepare_messages() to also apply
        provider role mapping.

        Accepts:
            - list[str] -> converts to [{'role':'user','content': str}, ...]
            - list[dict] with 'role' and 'content' -> passes through unchanged
            - list[dict] with only 'content' -> assumes role='user'

        Returns:
            list[{'role': str, 'content': str or list[...]}]
        """
        norm = []
        for m in msg_list:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                entry = {"role": role, "content": content}
                if m.get("cache"):
                    entry["cache"] = True
                norm.append(entry)
            else:
                # treat as plain user text
                norm.append({"role": "user", "content": str(m)})
        return norm

    def _map_roles(self, msg_list):
        """
        Translate ThoughtFlow roles to provider-native role strings.

        Uses the PROVIDER_ROLE_MAP lookup for the current service.  Roles
        without an explicit mapping entry pass through unchanged — if the
        provider rejects them, the API error is surfaced honestly rather
        than the role being silently dropped or rewritten.

        Args:
            msg_list: List of normalised message dicts (from _normalize_messages).

        Returns:
            list[dict]: New message dicts with translated roles.
        """
        role_map = PROVIDER_ROLE_MAP.get(self.service, {})
        if not role_map:
            return msg_list
        mapped = []
        for m in msg_list:
            m_copy = dict(m)
            m_copy["role"] = role_map.get(m["role"], m["role"])
            mapped.append(m_copy)
        return mapped

    def _prepare_messages(self, msg_list):
        """
        Normalise structure then translate roles for the current provider.

        Convenience pipeline: _normalize_messages() (structural) followed
        by _map_roles() (provider-aware).  All _call_* methods should use
        this instead of calling _normalize_messages() directly.

        Args:
            msg_list: Raw messages (strings, dicts, or a mix).

        Returns:
            list[dict]: Provider-ready message dicts.
        """
        normalized = self._normalize_messages(msg_list)
        return self._map_roles(normalized)

    def _prepare_messages_for_provider(self, msg_list):
        """
        Full message pipeline: normalize, map roles, apply cache wire adapters.

        All network _call_* methods use this so cache=True markers reach the
        provider in native form.
        """
        mapped = self._prepare_messages(msg_list)
        return apply_cache_markers(mapped, self.service)

    @staticmethod
    def _extract_message_text(message):
        """
        Prefer message content; fall back to reasoning when content is empty.

        Several OpenAI-compatible hosts (Cerebras gpt-oss, etc.) place the
        user-visible answer in message.reasoning when max_tokens is tight.
        """
        if not isinstance(message, dict):
            return str(message or "").strip()
        content = message.get("content")
        if content is not None and content != "":
            if isinstance(content, str):
                text = content.strip()
                if text:
                    return text
            else:
                return str(content).strip()
        reasoning = str(message.get("reasoning") or "").strip()
        return reasoning

    def _resolve_openai_transport(self, transport):
        """
        Build OpenAI-compatible URL and headers from transport context.

        Transport keys (base_url, extra_headers) never enter JSON bodies —
        they are split out by split_call_params before _call_* runs.
        """
        transport = transport or {}
        base_url = transport.get('base_url')
        extra_headers = transport.get('extra_headers')

        if base_url:
            url = base_url.rstrip('/') + '/chat/completions'
        else:
            url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        return url, headers, bool(base_url)

    @staticmethod
    def _schema_prompt_instruction(output_schema):
        """Build a system message instructing the model to return schema-conforming JSON.

        Used as a fallback for OpenAI-compatible servers that do not support
        the native response_format json_schema mechanism.
        """
        return {
            "role": "system",
            "content": (
                "You must respond with ONLY valid JSON (no markdown, no explanation) "
                "conforming to this JSON Schema:\n"
                + json.dumps(output_schema, separators=(',', ':'))
            ),
        }

    def call(self, msg_list, params={}, output_schema=None, stream=False):
        """
        Call the appropriate LLM API with the given messages and parameters.

        Args:
            msg_list (list): Messages to send to the LLM.
            params (dict): Provider-specific parameters (temperature, max_tokens,
                top_p, frequency_penalty, presence_penalty, etc.).  Per-call
                values override any defaults set in the constructor.
            output_schema (dict, optional): JSON Schema dict to enforce structured
                output. When provided, the LLM is constrained to return JSON
                matching this schema via the provider's native structured output
                mechanism (response_format for OpenAI/Groq/OpenRouter, tool-use
                wrapping for Anthropic). Providers without native support fall back
                to prompt injection.
            stream (bool): If True, return a generator yielding response chunks
                instead of waiting for the full response. Defaults to False.

        Returns:
            list[str]: Response strings (one per choice) when stream=False.
            generator: Yields string chunks when stream=True.
        """
        merged = merge_call_params(self.default_params, params)
        self.last_params = dict(merged)
        wire_params, transport = split_call_params(merged)

        # Compute the exchange signature up front (params are mutated by the
        # provider methods) so recording sees the canonical request.
        recording = self._record_memory is not None
        if recording:
            key, request = self._request_signature(msg_list, merged, output_schema)

        if stream:
            gen = self._stream(msg_list, wire_params, transport, output_schema)
            if recording:
                return self._record_stream(gen, key, request)
            return gen

        call_params = dict(wire_params)
        if output_schema:
            call_params['_output_schema'] = output_schema

        if self.service == 'openai':
            choices = self._call_openai(msg_list, call_params, transport)
        elif self.service == 'groq':
            choices = self._call_groq(msg_list, call_params, transport)
        elif self.service == 'anthropic':
            choices = self._call_anthropic(msg_list, call_params, transport)
        elif self.service == 'ollama':
            choices = self._call_ollama(msg_list, call_params, transport)
        elif self.service == 'gemini':
            choices = self._call_gemini(msg_list, call_params, transport)
        elif self.service == 'openrouter':
            choices = self._call_openrouter(msg_list, call_params, transport)
        else:
            raise ValueError("Unsupported service '{}'.".format(self.service))

        if recording:
            self._record_exchange(key, request, choices)
        return choices

    def _call_openai(self, msg_list, params, transport=None):
        url, headers, is_local = self._resolve_openai_transport(transport)
        output_schema = params.pop('_output_schema', None)

        messages = self._prepare_messages_for_provider(msg_list)
        if output_schema and is_local:
            messages = messages + [self._schema_prompt_instruction(output_schema)]

        payload = {
            "model": self.model,
            "messages": messages,
            **params
        }
        if output_schema and not is_local:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.get("name", "response"),
                    "strict": True,
                    "schema": output_schema,
                },
            }

        data = json.dumps(payload).encode("utf-8")
        res = self._send_request(url, data, headers)
        choices = [
            self._extract_message_text(a.get("message", {}))
            for a in res.get("choices", [])
        ]
        return choices

    def _call_groq(self, msg_list, params, transport=None):
        url = "https://api.groq.com/openai/v1/chat/completions"

        output_schema = params.pop('_output_schema', None)
        payload = {
            "model": self.model,
            "messages": self._prepare_messages_for_provider(msg_list),
            **params
        }
        if output_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.get("name", "response"),
                    "strict": True,
                    "schema": output_schema,
                },
            }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Groq/Python 0.9.0",
        }
        res = self._send_request(url, data, headers)
        choices = [
            self._extract_message_text(a.get("message", {}))
            for a in res.get("choices", [])
        ]
        return choices

    def _split_system_messages(self, msg_list):
        """Extract system prompts for Anthropic's top-level ``system`` field."""
        system_parts = []
        system_messages = []
        conversation = []
        for msg in self._normalize_messages(msg_list):
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if content:
                    system_messages.append(dict(msg))
                    if isinstance(content, str):
                        system_parts.append(content)
                    else:
                        system_parts.append(str(content))
            else:
                conversation.append(msg)
        return system_parts, system_messages, self._map_roles(conversation)

    def _call_anthropic(self, msg_list, params, transport=None):
        url = "https://api.anthropic.com/v1/messages"

        output_schema = params.pop('_output_schema', None)
        system_parts, system_messages, messages = self._split_system_messages(msg_list)
        messages = apply_cache_markers(messages, "anthropic")

        anthropic_params = pick_anthropic_wire_params(params)
        payload = {
            "model": self.model,
            "max_tokens": anthropic_params.get("max_tokens", 1024),
            "messages": messages,
        }
        for key in ("temperature", "top_p", "top_k", "stop_sequences"):
            if key in anthropic_params:
                payload[key] = anthropic_params[key]

        system_value = format_anthropic_system(system_parts, system_messages)
        if system_value is not None:
            payload["system"] = system_value

        # Anthropic uses a tool-use pattern for structured output: define a
        # tool whose input_schema is the desired output shape, then force the
        # model to call it via tool_choice.
        if output_schema:
            schema_name = output_schema.get("name", "structured_response")
            payload["tools"] = [{
                "name": schema_name,
                "description": "Return a structured response matching the schema.",
                "input_schema": output_schema,
            }]
            payload["tool_choice"] = {"type": "tool", "name": schema_name}

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)

        # When structured output is used, the response is in tool_use blocks
        if output_schema:
            choices = []
            for block in res.get("content", []):
                if block.get("type") == "tool_use":
                    choices.append(json.dumps(block.get("input", {})))
                elif block.get("type") == "text":
                    choices.append(block.get("text", ""))
            return choices or [""]

        choices = [c.get("text", "") for c in res.get("content", [])]
        return choices

    def _call_gemini(self, msg_list, params, transport=None):
        """
        Calls Google Gemini/SVertexAI chat-supported models via REST API.
        Requires self.api_key to be set.
        """
        call_params = dict(params)
        call_params.pop('_output_schema', None)
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}".format(self.model, self.api_key)
        gemini_msgs = []
        for m in self._prepare_messages_for_provider(msg_list):
            gemini_msgs.append({
                "role": m["role"],
                "parts": [{"text": str(m["content"])}] if isinstance(m["content"], str) else m["content"]
            })
        generation_config = build_gemini_generation_config(call_params)
        payload = {"contents": gemini_msgs}
        if generation_config:
            payload["generationConfig"] = generation_config
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        choices = []
        for cand in res.get("candidates", []):
            parts = cand.get("content", {}).get("parts", [])
            text = "".join([p.get("text", "") for p in parts])
            choices.append(text)
        return choices

    def _call_openrouter(self, msg_list, params, transport=None):
        """
        Calls an LLM via the OpenRouter API. Requires self.api_key.
        API docs: https://openrouter.ai/docs
        Model list: https://openrouter.ai/docs#models
        """
        transport = transport or {}
        output_schema = params.pop('_output_schema', None)
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": self._prepare_messages_for_provider(msg_list),
            **params
        }
        if output_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.get("name", "response"),
                    "strict": True,
                    "schema": output_schema,
                },
            }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": transport.get("referer", "https://your-app.com"),
            "X-Title": transport.get("title", "ThoughtFlow"),
        }
        res = self._send_request(url, data, headers)
        choices = [
            self._extract_message_text(a.get("message", {}))
            for a in res.get("choices", [])
        ]
        return choices

    def _call_ollama(self, msg_list, params, transport=None):
        """
        Calls a local model served via Ollama (http://localhost:11434 by default).
        Expects no authentication. Ollama messages format is like OpenAI's.
        """
        output_schema = params.pop('_output_schema', None)
        base_url = params.get("ollama_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/chat"
        payload = {
            "model": self.model,
            "messages": self._prepare_messages_for_provider(msg_list),
            "stream": False,
            **{k: v for k, v in params.items() if k not in ("ollama_url", "model")}
        }
        # Ollama supports structured output via the 'format' key
        if output_schema:
            payload["format"] = output_schema
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)

        def _message_to_choice(message: dict) -> str:
            """
            Convert an Ollama message to include tool calls in the content.
            """
            tools = message.get("tool_calls", [])
            if not tools:
                return message.get("content", "")
                
            output = []
            for tool in tools:
                func = tool.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                output.append({"name": func.get("name", ""), "arguments": args})
            return json.dumps({"tool_calls": output})
            
        # Ollama returns {"message": {...}, ...} or {"choices": [{...}]}
        # Prefer OpenAI-style extraction if available, else fallback
        if "choices" in res:
            choices = [_message_to_choice(a["message"]) for a in res.get("choices", [])]
        elif "message" in res:
            # single result
            choices = [_message_to_choice(res["message"])]
        elif "response" in res:
            # streaming/fallback
            choices = [res["response"]]
        else:
            choices = []
        return choices

    def _stream(self, msg_list, wire_params, transport, output_schema=None):
        """
        Stream a response from the LLM, yielding text chunks as they arrive.

        Opens an HTTP connection with stream=True and parses the Server-Sent
        Events (SSE) protocol that OpenAI-compatible APIs use. Each yielded
        value is a string fragment of the response.

        Currently supports OpenAI, Groq, OpenRouter, and Ollama. Anthropic
        and Gemini use different streaming protocols that may be added later;
        for now they fall back to a single-yield non-streaming call.

        Args:
            msg_list (list): Messages to send.
            wire_params (dict): Model params for the wire (transport already split).
            transport (dict): Transport context (base_url, referer, etc.).
            output_schema (dict, optional): Structured output schema.

        Yields:
            str: Text chunks as they arrive from the provider.
        """
        transport = transport or {}
        params = dict(wire_params)

        # For providers without SSE streaming support, fall back to full call
        if self.service in ('anthropic', 'gemini'):
            call_params = dict(params)
            if output_schema:
                call_params['_output_schema'] = output_schema
            if self.service == 'anthropic':
                result = self._call_anthropic(msg_list, call_params, transport)
            else:
                result = self._call_gemini(msg_list, call_params, transport)
            for text in result:
                yield text
            return

        is_local = False

        # Build the URL and headers per provider
        if self.service == 'openai':
            url, headers, is_local = self._resolve_openai_transport(transport)
        elif self.service == 'groq':
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "Groq/Python 0.9.0",
            }
        elif self.service == 'openrouter':
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "HTTP-Referer": transport.get("referer", "https://your-app.com"),
                "X-Title": transport.get("title", "ThoughtFlow"),
            }
        elif self.service == 'ollama':
            base_url = params.get("ollama_url", "http://localhost:11434")
            url = base_url.rstrip('/') + "/api/chat"
            headers = {"Content-Type": "application/json"}
        else:
            raise ValueError("Streaming not supported for service '{}'.".format(self.service))

        # Build the payload
        if self.service == 'ollama':
            payload = {
                "model": self.model,
                "messages": self._prepare_messages_for_provider(msg_list),
                "stream": True,
                **{k: v for k, v in params.items() if k not in ("ollama_url", "model")}
            }
        else:
            messages = self._prepare_messages_for_provider(msg_list)
            if output_schema and is_local:
                messages = messages + [self._schema_prompt_instruction(output_schema)]

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                **params
            }
            if output_schema and not is_local:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.get("name", "response"),
                        "strict": True,
                        "schema": output_schema,
                    },
                }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            open_kwargs = {}
            if self.request_timeout is not None:
                open_kwargs["timeout"] = self.request_timeout
            response = urllib.request.urlopen(req, **open_kwargs)
        except Exception:
            return

        # Parse the SSE / NDJSON stream
        try:
            if self.service == 'ollama':
                # Ollama uses newline-delimited JSON
                for line in self._iter_lines(response):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
            else:
                # OpenAI-compatible SSE format
                for line in self._iter_lines(response):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
        finally:
            response.close()

    def _iter_lines(self, response):
        """
        Yield lines from an HTTP response, handling buffered reads.

        Reads the response in small chunks and yields complete lines. This
        avoids loading the entire stream into memory at once.

        Args:
            response: An open urllib response object.

        Yields:
            str: Individual lines from the response.
        """
        buf = ""
        while True:
            chunk = response.read(4096)
            if not chunk:
                if buf:
                    yield buf
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                yield line.strip()

    def _send_request(self, url, data, headers):
        """
        Send an HTTP POST request and return the parsed JSON response.

        Updates last_error and last_usage on every call. Invokes on_usage
        when configured and the response includes a usage block.
        """
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            open_kwargs = {}
            if self.request_timeout is not None:
                open_kwargs["timeout"] = self.request_timeout
            with urllib.request.urlopen(req, **open_kwargs) as response:
                response_data = response.read().decode("utf-8")
                try:
                    parsed = json.loads(response_data)
                except json.JSONDecodeError:
                    self.last_error = "Non-JSON response"
                    self.last_usage = None
                    return {"error": "Non-JSON response", "response_data": response_data}

                if isinstance(parsed, dict) and "error" in parsed:
                    err = parsed["error"]
                    self.last_error = str(err)[:500]
                    self.last_usage = None
                    return parsed

                self.last_error = None
                self.last_usage = normalize_usage(parsed, self.service, self.model)
                if self.on_usage and callable(self.on_usage) and self.last_usage:
                    self.on_usage(self.last_usage)
                return parsed

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            print("HTTP Error:", error_msg)
            self.last_error = error_msg[:500]
            self.last_usage = None
            try:
                return {"error": json.loads(error_msg) if error_msg else "Unknown HTTP error"}
            except json.JSONDecodeError:
                return {"error": error_msg or "Unknown HTTP error"}
        except Exception as e:
            self.last_error = str(e)[:500]
            self.last_usage = None
            return {"error": str(e)}


class ReplayLLM(LLM):
    """
    An LLM that serves recorded responses instead of calling the network.

    ReplayLLM is the other half of ThoughtFlow's record/replay system. Feed
    it a MEMORY that contains recorded exchanges (created via LLM.record),
    and it answers every call() by content-hash lookup: same request in,
    same response out. Deterministic, offline, instant.

    Repeated identical requests are served in their recorded order; once
    recordings for a key are exhausted, the last response repeats (a given
    request always has an answer once it has one).

    Construct via LLM.replay(memory) or directly.

    Example:
        >>> live = LLM("openai:gpt-4o", key="sk-...").record(memory)
        >>> memory = my_flow(memory)          # hits the API, records
        >>> memory.to_json("session.json")
        >>>
        >>> recorded = MEMORY.from_json("session.json")
        >>> llm = LLM.replay(recorded)
        >>> memory2 = my_flow(MEMORY())       # no network, same outputs
    """

    def __init__(self, memory, on_miss='raise', model_id=None):
        """
        Args:
            memory: MEMORY containing recorded 'chat' exchanges.
            on_miss: 'raise' to raise ReplayMissError on unrecorded requests
                (default — fail loudly), or a live LLM instance to fall back
                to (useful for re-recording drifted flows).
            model_id: 'service:model' to replay as. Optional when the memory
                contains recordings from exactly one model.
        """
        exchanges = memory.get_exchanges(kind='chat')

        identities = {(e.get('service'), e.get('model')) for e in exchanges}
        if model_id is not None:
            service, model = model_id.split(':', 1)
        elif len(identities) == 1:
            service, model = next(iter(identities))
        elif len(identities) == 0:
            service, model = 'replay', 'empty'
        else:
            raise ValueError(
                "Memory contains recordings from multiple models ({}). "
                "Pass model_id='service:model' to choose one.".format(
                    ", ".join(sorted("{}:{}".format(s, m) for s, m in identities))
                )
            )

        super().__init__(model_id="{}:{}".format(service, model), key='replay')
        self.on_miss = on_miss

        # key -> list of recorded responses, in chronological order
        self._responses = {}
        self._cursor = {}
        for e in exchanges:
            if (e.get('service'), e.get('model')) != (service, model):
                continue
            self._responses.setdefault(e['key'], []).append(e.get('response', []))
            self._cursor[e['key']] = 0

    def call(self, msg_list, params={}, output_schema=None, stream=False):
        """
        Serve a recorded response for the given request.

        Matches by content hash of (normalized messages, params minus
        transport keys, output_schema, service, model) — exactly the key
        used at record time.
        """
        merged = merge_call_params(self.default_params, params)
        self.last_params = dict(merged)

        key, _request = self._request_signature(msg_list, merged, output_schema)
        recorded = self._responses.get(key)

        if recorded is None:
            if self.on_miss == 'raise' or self.on_miss is None:
                raise ReplayMissError(
                    "No recorded response for this request (key={}). The flow "
                    "has drifted from the recording. Re-record the session, or "
                    "construct the ReplayLLM with on_miss=<live LLM> to fall "
                    "back.".format(key)
                )
            # Fall back to a live LLM
            return self.on_miss.call(
                msg_list, params=params, output_schema=output_schema, stream=stream
            )

        idx = min(self._cursor[key], len(recorded) - 1)
        self._cursor[key] += 1
        choices = list(recorded[idx])

        if stream:
            def _single_yield():
                for text in choices[:1]:
                    yield text
            return _single_yield()
        return choices


class OpenAICompatibleLLM(LLM):
    """Convenience subclass for connecting to any OpenAI-compatible server.

    Wraps LLM with the ``openai`` service and a custom ``base_url`` so you
    can talk to local inference servers (MLX, vLLM, llama.cpp, LM Studio,
    etc.) without remembering the ``service:model`` format or dummy key.

    Example::

        from thoughtflow import OpenAICompatibleLLM

        llm = OpenAICompatibleLLM(
            model="mlx-community/Llama-3-8B-Instruct",
            base_url="http://127.0.0.1:8765/v1",
        )
        choices = llm.call([{"role": "user", "content": "Hello!"}])
    """

    def __init__(self, model, base_url, key="dummy", **kwargs):
        super().__init__(
            model_id="openai:{}".format(model),
            key=key,
            base_url=base_url,
            **kwargs,
        )

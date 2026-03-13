"""
LLM class for ThoughtFlow.

A unified interface for calling various language model services.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error


class LLM:
    """
    The LLM class is designed to interface with various language model services.
    
    Attributes:
        service (str): The name of the service provider (e.g., 'openai', 'groq', 'anthropic').
        model (str): The specific model to be used within the service.
        api_key (str): The API key for authenticating requests.
        api_secret (str): The API secret for additional authentication.
        last_params (dict): Stores the parameters used in the last API call.

    Methods:
        __init__(model_id, key, secret):
            Initializes the LLM instance with a model ID, API key, and secret.
        
        call(msg_list, params):
            Calls the appropriate API based on the service with the given message list and parameters.
        
        _call_openai(msg_list, params):
            Sends a request to the OpenAI API with the specified messages and parameters.
        
        _call_groq(msg_list, params):
            Sends a request to the Groq API with the specified messages and parameters.
        
        _call_anthropic(msg_list, params):
            Sends a request to the Anthropic API with the specified messages and parameters.
        
        _send_request(url, data, headers):
            Helper function to send HTTP requests to the specified URL with data and headers.
    """
    def __init__(self, model_id='', key='API_KEY', secret='API_SECRET'):
        # Parse model ID and initialize service and model name
        if ':' not in model_id: model_id = 'openai:gpt-4-turbo'
        
        splitted = model_id.split(':') 
        self.service = splitted[0]
        self.model = ''.join(splitted[1:]) 
        self.api_key = key
        self.api_secret = secret
        self.last_params = {} 
        # Make the object directly callable
        self.__call__ = self.call

    def _normalize_messages(self, msg_list):
        """
        Accepts either:
        - list[str] -> converts to [{'role':'user','content': str}, ...]
        - list[dict] with 'role' and 'content' -> passes through unchanged
        - list[dict] with only 'content' -> assumes role='user'
        Returns: list[{'role': str, 'content': str or list[...]}]
        """
        norm = []
        for m in msg_list:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                norm.append({"role": role, "content": content})
            else:
                # treat as plain user text
                norm.append({"role": "user", "content": str(m)})
        return norm

    def call(self, msg_list, params={}, output_schema=None, stream=False):
        """
        Call the appropriate LLM API with the given messages and parameters.

        Args:
            msg_list (list): Messages to send to the LLM.
            params (dict): Provider-specific parameters (temperature, max_tokens, etc.).
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
        self.last_params = dict(params)

        if stream:
            return self._stream(msg_list, params, output_schema)

        # Merge output_schema into params for provider-specific handling
        call_params = dict(params)
        if output_schema:
            call_params['_output_schema'] = output_schema

        if self.service == 'openai':
            return self._call_openai(msg_list, call_params)
        elif self.service == 'groq':
            return self._call_groq(msg_list, call_params)
        elif self.service == 'anthropic':
            return self._call_anthropic(msg_list, call_params)
        elif self.service == 'ollama':
            return self._call_ollama(msg_list, call_params)
        elif self.service == 'gemini':
            return self._call_gemini(msg_list, call_params)
        elif self.service == 'openrouter':
            return self._call_openrouter(msg_list, call_params)
        else:
            raise ValueError("Unsupported service '{}'.".format(self.service))

    def _call_openai(self, msg_list, params):
        url = "https://api.openai.com/v1/chat/completions"

        # Extract and apply structured output schema if present
        output_schema = params.pop('_output_schema', None)
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
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
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_groq(self, msg_list, params):
        url = "https://api.groq.com/openai/v1/chat/completions"

        output_schema = params.pop('_output_schema', None)
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
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
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_anthropic(self, msg_list, params):
        url = "https://api.anthropic.com/v1/messages"

        output_schema = params.pop('_output_schema', None)
        payload = {
            "model": self.model,
            "max_tokens": params.get("max_tokens", 1024),
            "messages": self._normalize_messages(msg_list),
        }

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

    def _call_gemini(self, msg_list, params):
        """
        Calls Google Gemini/SVertexAI chat-supported models via REST API.
        Requires self.api_key to be set.
        """
        params.pop('_output_schema', None)
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}".format(self.model, self.api_key)
        # Gemini expects a list of "contents" alternating user/assistant
        # We collapse the messages into a sequence of dicts as required by Gemini
        # Gemini wants [{"role": "user/assistant", "parts": [{"text": ...}]}]
        gemini_msgs = []
        for m in self._normalize_messages(msg_list):
            # Google's role scheme: "user" or "model"
            g_role = {"user": "user", "assistant": "model", "system": "user"}.get(m["role"], "user")
            gemini_msgs.append({
                "role": g_role,
                "parts": [{"text": str(m["content"])}] if isinstance(m["content"], str) else m["content"]
            })
        payload = {
            "contents": gemini_msgs,
            **{k: v for k, v in params.items() if k != "model"}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Gemini returns { "candidates": [ { "content": { "parts": [ { "text": ... } ] } } ] }
        choices = []
        for cand in res.get("candidates", []):
            parts = cand.get("content", {}).get("parts", [])
            text = "".join([p.get("text", "") for p in parts])
            choices.append(text)
        return choices

    def _call_openrouter(self, msg_list, params):
        """
        Calls an LLM via the OpenRouter API. Requires self.api_key.
        API docs: https://openrouter.ai/docs
        Model list: https://openrouter.ai/docs#models
        """
        output_schema = params.pop('_output_schema', None)
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
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
            "HTTP-Referer": params.get("referer", "https://your-app.com"),
            "X-Title": params.get("title", "Thoughtflow"),
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_ollama(self, msg_list, params):
        """
        Calls a local model served via Ollama (http://localhost:11434 by default).
        Expects no authentication. Ollama messages format is like OpenAI's.
        """
        output_schema = params.pop('_output_schema', None)
        base_url = params.get("ollama_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/chat"
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
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
        # Ollama returns {"message": {...}, ...} or {"choices": [{...}]}
        # Prefer OpenAI-style extraction if available, else fallback
        if "choices" in res:
            choices = [a["message"]["content"] for a in res.get("choices", [])]
        elif "message" in res:
            # single result
            msg = res["message"]
            choices = [msg.get("content", "")]
        elif "response" in res:
            # streaming/fallback
            choices = [res["response"]]
        else:
            choices = []
        return choices

    def _stream(self, msg_list, params, output_schema=None):
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
            params (dict): Provider-specific parameters.
            output_schema (dict, optional): Structured output schema.

        Yields:
            str: Text chunks as they arrive from the provider.
        """
        # For providers without SSE streaming support, fall back to full call
        if self.service in ('anthropic', 'gemini'):
            call_params = dict(params)
            if output_schema:
                call_params['_output_schema'] = output_schema
            if self.service == 'anthropic':
                result = self._call_anthropic(msg_list, call_params)
            else:
                result = self._call_gemini(msg_list, call_params)
            for text in result:
                yield text
            return

        # Build the URL and headers per provider
        if self.service == 'openai':
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            }
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
                "HTTP-Referer": params.get("referer", "https://your-app.com"),
                "X-Title": params.get("title", "Thoughtflow"),
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
                "messages": self._normalize_messages(msg_list),
                "stream": True,
                **{k: v for k, v in params.items() if k not in ("ollama_url", "model")}
            }
        else:
            payload = {
                "model": self.model,
                "messages": self._normalize_messages(msg_list),
                "stream": True,
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
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            response = urllib.request.urlopen(req)
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
        """Send an HTTP POST request and return the parsed JSON response."""
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")  
                # Attempt to parse JSON response; handle plain-text responses
                try:
                    return json.loads(response_data)  # Parse JSON response
                except json.JSONDecodeError:
                    # If response is not JSON, return it as-is in a structured format
                    return {"error": "Non-JSON response", "response_data": response_data}
                
        except urllib.error.HTTPError as e:
            # Return the error details in case of an HTTP error
            error_msg = e.read().decode("utf-8")
            print("HTTP Error:", error_msg)  # Log HTTP error for debugging
            return {"error": json.loads(error_msg) if error_msg else "Unknown HTTP error"}
        except Exception as e:
            return {"error": str(e)}  

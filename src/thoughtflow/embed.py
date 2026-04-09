"""
EMBED class for ThoughtFlow.

A unified interface for calling various text embedding services.
Mirrors the LLM class architecture but targets embedding endpoints
instead of chat completion endpoints.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error


class EMBED:
    """
    Unified interface for text embedding across multiple providers.

    EMBED is the embedding counterpart to LLM. Where LLM sends messages to a
    text generation endpoint and returns a completion, EMBED sends text to an
    embedding endpoint and returns a vector (list of floats). It follows the
    same multi-provider pattern as LLM — a single class that routes to OpenAI,
    Groq, Ollama, Gemini, or OpenRouter based on a model_id string.

    Attributes:
        service (str): The provider name (e.g., 'openai', 'ollama', 'gemini').
        model (str): The specific embedding model to use.
        api_key (str): The API key for authentication.
        api_secret (str): Optional API secret for additional authentication.
        last_params (dict): Parameters used in the most recent call.
        last_meta (dict): Metadata from the most recent call (dimensions,
            token count, etc.) when the provider supplies it.

    Example:
        >>> embed = EMBED("openai:text-embedding-3-small", key="sk-...")
        >>> vector = embed.call("Hello world")
        >>> len(vector)  # e.g., 1536
        1536

        >>> vectors = embed.call(["Hello", "World"])
        >>> len(vectors)
        2

        >>> embed = EMBED("ollama:nomic-embed-text")
        >>> vector = embed.call("Local embedding")
    """

    def __init__(self, model_id='', key='API_KEY', secret='API_SECRET', **kwargs):
        """
        Initialize an EMBED instance with a model ID and credentials.

        The model_id uses the same 'service:model' format as LLM. The service
        prefix determines which provider API to call; the model suffix is
        passed to the provider's embedding endpoint.

        Args:
            model_id (str): Provider and model in 'service:model' format.
                Examples: 'openai:text-embedding-3-small', 'ollama:nomic-embed-text'.
                Defaults to 'openai:text-embedding-3-small' if no colon is present.
            key (str): API key for the provider.
            secret (str): Optional API secret for additional authentication.
            **kwargs: Default parameters applied to every call (e.g. base_url,
                extra_headers, dimensions).  Per-call params override these.
        """
        if ':' not in model_id:
            model_id = 'openai:text-embedding-3-small'

        parts = model_id.split(':')
        self.service = parts[0]
        self.model = ':'.join(parts[1:])
        self.api_key = key
        self.api_secret = secret
        self.last_params = {}
        self.last_meta = {}
        self.default_params = {}

        for k, v in kwargs.items():
            if v is not None:
                self.default_params[k] = v

        self.__call__ = self.call

    def call(self, text, params=None):
        """
        Generate embeddings for the given text input.

        Accepts a single string or a list of strings. Returns a single vector
        (list of floats) for a single string, or a list of vectors for a list
        of strings.

        Args:
            text (str or list[str]): The text(s) to embed.
            params (dict, optional): Additional parameters passed to the
                provider (e.g., dimensions, encoding_format). Defaults to {}.

        Returns:
            list[float]: A single embedding vector when text is a string.
            list[list[float]]: A list of embedding vectors when text is a list.

        Example:
            >>> embed = EMBED("openai:text-embedding-3-small", key="sk-...")
            >>> v = embed.call("Hello")
            >>> isinstance(v[0], float)
            True
            >>> vs = embed.call(["Hello", "World"])
            >>> len(vs)
            2
        """
        params = {**self.default_params, **(params or {})}
        self.last_params = dict(params)
        self.last_meta = {}

        # Track whether the caller passed a single string so we can unwrap
        single_input = isinstance(text, str)
        texts = [text] if single_input else list(text)

        if self.service == 'openai':
            vectors = self._call_openai(texts, params)
        elif self.service == 'ollama':
            vectors = self._call_ollama(texts, params)
        elif self.service == 'gemini':
            vectors = self._call_gemini(texts, params)
        elif self.service == 'groq':
            vectors = self._call_groq(texts, params)
        elif self.service == 'openrouter':
            vectors = self._call_openrouter(texts, params)
        else:
            raise ValueError("Unsupported embedding service '{}'.".format(self.service))

        if single_input and vectors:
            return vectors[0]
        return vectors

    # ------------------------------------------------------------------ #
    # Provider-specific implementations
    # ------------------------------------------------------------------ #

    def _call_openai(self, texts, params):
        """
        Call the OpenAI (or OpenAI-compatible) embeddings endpoint.

        Uses the /v1/embeddings endpoint. Supports the 'dimensions' parameter
        for models that allow truncated embeddings (e.g., text-embedding-3-*).
        When base_url is provided, targets that server instead of cloud OpenAI.

        Args:
            texts (list[str]): Texts to embed.
            params (dict): Additional API parameters.

        Returns:
            list[list[float]]: Embedding vectors ordered by input index.
        """
        base_url = params.pop('base_url', None)
        extra_headers = params.pop('extra_headers', None)

        if base_url:
            url = base_url.rstrip('/') + '/embeddings'
        else:
            url = "https://api.openai.com/v1/embeddings"

        payload = {
            "model": self.model,
            "input": texts,
        }
        for key in ("dimensions", "encoding_format"):
            if key in params:
                payload[key] = params[key]

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        res = self._send_request(url, data, headers)
        return self._parse_openai_response(res)

    def _call_groq(self, texts, params):
        """
        Call the Groq embeddings endpoint (OpenAI-compatible format).

        Args:
            texts (list[str]): Texts to embed.
            params (dict): Additional API parameters.

        Returns:
            list[list[float]]: Embedding vectors ordered by input index.
        """
        url = "https://api.groq.com/openai/v1/embeddings"
        payload = {
            "model": self.model,
            "input": texts,
        }
        for key in ("dimensions", "encoding_format"):
            if key in params:
                payload[key] = params[key]

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        return self._parse_openai_response(res)

    def _call_openrouter(self, texts, params):
        """
        Call the OpenRouter embeddings endpoint (OpenAI-compatible format).

        Args:
            texts (list[str]): Texts to embed.
            params (dict): Additional API parameters.

        Returns:
            list[list[float]]: Embedding vectors ordered by input index.
        """
        url = "https://openrouter.ai/api/v1/embeddings"
        payload = {
            "model": self.model,
            "input": texts,
        }
        for key in ("dimensions", "encoding_format"):
            if key in params:
                payload[key] = params[key]

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": params.get("referer", "https://your-app.com"),
            "X-Title": params.get("title", "Thoughtflow"),
        }
        res = self._send_request(url, data, headers)
        return self._parse_openai_response(res)

    def _call_ollama(self, texts, params):
        """
        Call a local Ollama embedding endpoint.

        Ollama's /api/embed endpoint accepts a list of texts and returns
        embeddings for each. No authentication required for local instances.

        Args:
            texts (list[str]): Texts to embed.
            params (dict): Additional parameters. Supports 'ollama_url' to
                override the default localhost address.

        Returns:
            list[list[float]]: Embedding vectors.
        """
        base_url = params.get("ollama_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/embed"
        payload = {
            "model": self.model,
            "input": texts,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        res = self._send_request(url, data, headers)

        # Ollama returns {"embeddings": [[...], [...]], ...}
        vectors = res.get("embeddings", [])
        self.last_meta = {
            "total_duration": res.get("total_duration"),
            "load_duration": res.get("load_duration"),
            "prompt_eval_count": res.get("prompt_eval_count"),
        }
        return vectors

    def _call_gemini(self, texts, params):
        """
        Call the Google Gemini embedding endpoint.

        Uses the batchEmbedContents method for efficient batch embedding.

        Args:
            texts (list[str]): Texts to embed.
            params (dict): Additional API parameters. Supports 'task_type'
                (e.g., 'RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY').

        Returns:
            list[list[float]]: Embedding vectors.
        """
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "{}:batchEmbedContents?key={}".format(self.model, self.api_key)
        )
        task_type = params.get("task_type", "RETRIEVAL_DOCUMENT")

        requests_list = []
        for t in texts:
            requests_list.append({
                "model": "models/" + self.model,
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
            })

        payload = {"requests": requests_list}
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        res = self._send_request(url, data, headers)

        # Gemini returns {"embeddings": [{"values": [...]}, ...]}
        vectors = []
        for emb in res.get("embeddings", []):
            vectors.append(emb.get("values", []))
        return vectors

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _parse_openai_response(self, res):
        """
        Parse an OpenAI-format embedding response.

        OpenAI, Groq, and OpenRouter all return the same response shape:
        {"data": [{"embedding": [...], "index": 0}, ...], "usage": {...}}.
        Vectors are sorted by index to match input order.

        Args:
            res (dict): The raw JSON response from the provider.

        Returns:
            list[list[float]]: Embedding vectors ordered by input index.
        """
        items = res.get("data", [])
        # Sort by index to guarantee input order
        items.sort(key=lambda x: x.get("index", 0))
        vectors = [item.get("embedding", []) for item in items]

        # Capture metadata
        usage = res.get("usage", {})
        self.last_meta = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "model": res.get("model"),
        }
        return vectors

    def _send_request(self, url, data, headers):
        """
        Send an HTTP POST request and return the parsed JSON response.

        Mirrors the LLM class's _send_request method. Handles JSON parsing
        errors and HTTP errors gracefully.

        Args:
            url (str): The endpoint URL.
            data (bytes): The JSON-encoded request body.
            headers (dict): HTTP headers.

        Returns:
            dict: Parsed JSON response, or an error dict on failure.
        """
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")
                try:
                    return json.loads(response_data)
                except json.JSONDecodeError:
                    return {
                        "error": "Non-JSON response",
                        "response_data": response_data,
                    }

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            try:
                return {"error": json.loads(error_msg)}
            except (json.JSONDecodeError, ValueError):
                return {"error": error_msg or "Unknown HTTP error"}
        except Exception as e:
            return {"error": str(e)}

    def __str__(self):
        """Return a concise string representation."""
        return "EMBED({}:{})".format(self.service, self.model)

    def __repr__(self):
        """Return a detailed string representation."""
        return "EMBED(service='{}', model='{}')".format(self.service, self.model)

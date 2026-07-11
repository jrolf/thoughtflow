"""
CerebrasLLM — Cerebras inference with Cloudflare-safe defaults.

Cerebras exposes an OpenAI-compatible API. Cloudflare returns HTTP 1010 when
User-Agent is missing. This class sets a safe default header and optional
auth-key fallback for preview-tier key rotation.
"""

from __future__ import annotations

from thoughtflow.llm import OpenAICompatibleLLM

DEFAULT_BASE_URL = "https://api.cerebras.ai/v1"
DEFAULT_USER_AGENT = "ThoughtFlow/1.0"

_AUTH_FAILURE_MARKERS = ("401", "403", "unauthorized", "forbidden", "api key", "invalid")


class CerebrasLLM(OpenAICompatibleLLM):
    """
    Cerebras inference with Cloudflare-safe defaults.

    Subclasses OpenAICompatibleLLM so all OpenAI-compat param passthrough and
    prompt caching behavior applies unchanged.

    Args:
        model (str): Cerebras model slug (e.g. gpt-oss-120b, zai-glm-4.7).
        key (str): CEREBRAS_API_KEY.
        base_url (str): API base URL (default https://api.cerebras.ai/v1).
        fallback_keys (list): Optional alternate API keys tried on auth failure only.
        **kwargs: Model and transport params (reasoning_effort, max_tokens, ...).
    """

    def __init__(self, model, key, base_url=None, fallback_keys=None, **kwargs):
        headers = dict(kwargs.pop("extra_headers", None) or {})
        headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        super().__init__(
            model=model,
            base_url=base_url or DEFAULT_BASE_URL,
            key=key,
            extra_headers=headers,
            **kwargs,
        )
        self._fallback_keys = list(fallback_keys or [])

    @staticmethod
    def _is_auth_failure(response):
        """Return True when the response looks like an authentication failure."""
        if not isinstance(response, dict) or "error" not in response:
            return False
        text = str(response["error"]).lower()
        return any(marker in text for marker in _AUTH_FAILURE_MARKERS)

    def _send_request(self, url, data, headers):
        """
        Send request with optional auth-key fallback.

        Retries alternate keys only on auth failures — not rate limits or
        transport errors.
        """
        response = super()._send_request(url, data, headers)
        if not self._is_auth_failure(response):
            return response

        for fb_key in self._fallback_keys:
            if fb_key == self.api_key:
                continue
            retry_headers = dict(headers)
            if "Authorization" in retry_headers:
                retry_headers["Authorization"] = "Bearer " + fb_key
            response = super()._send_request(url, data, retry_headers)
            if not self._is_auth_failure(response):
                self.api_key = fb_key
                break
        return response

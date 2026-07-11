"""
Shared helpers for live integration smoke tests.

Skips (rather than fails) when the failure looks like an API key or account
problem. Fails loudly on empty responses and transport/code issues so regressions
surface in CI when integration tests are enabled.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest

# Substrings that suggest the caller's key, billing, or account is the problem.
_ACCOUNT_ERROR_MARKERS = (
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "api key",
    "authentication",
    "permission",
    "user not found",
    "billing",
    "quota",
    "insufficient",
    "model_not_found",
    "does not exist or you do not have access",
)


def is_account_or_auth_error(error_text):
    """
    Return True when an error string looks like a key or account issue.

    Used to skip integration tests instead of failing the suite when credentials
    are missing, expired, or lack model access.
    """
    if not error_text:
        return False
    text = str(error_text).lower()
    return any(marker in text for marker in _ACCOUNT_ERROR_MARKERS)


def ollama_reachable(host=None):
    """Return True when a local Ollama server responds on /api/tags."""
    base = (host or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    try:
        req = urllib.request.Request(base + "/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def assert_llm_smoke(llm, result, provider):
    """
    Assert a live LLM call returned non-empty text.

    Skips on auth/account errors via last_error. Fails on empty choices so code
    regressions are not masked as skips.
    """
    if isinstance(result, dict) and "error" in result:
        err = result.get("error")
        if is_account_or_auth_error(err):
            pytest.skip("{}: API key or account issue ({})".format(provider, err))
        pytest.fail("{}: unexpected error response ({})".format(provider, err))

    if not isinstance(result, list) or not any(str(c).strip() for c in result):
        err = getattr(llm, "last_error", None)
        if is_account_or_auth_error(err):
            pytest.skip("{}: API key or account issue ({})".format(provider, err))
        pytest.fail(
            "{}: empty LLM response (last_error={})".format(provider, err)
        )


def assert_embed_smoke(embed, vector, provider):
    """
    Assert a live EMBED call returned a numeric vector.

    Skips on auth/account errors via last_error when present.
    """
    if isinstance(vector, dict) and "error" in vector:
        err = vector.get("error")
        if is_account_or_auth_error(err):
            pytest.skip("{}: API key or account issue ({})".format(provider, err))
        pytest.fail("{}: unexpected error response ({})".format(provider, err))

    if (
        not isinstance(vector, list)
        or len(vector) == 0
        or not isinstance(vector[0], (int, float))
    ):
        err = getattr(embed, "last_error", None)
        if is_account_or_auth_error(err):
            pytest.skip("{}: API key or account issue ({})".format(provider, err))
        pytest.fail(
            "{}: empty or invalid embedding (last_error={})".format(provider, err)
        )

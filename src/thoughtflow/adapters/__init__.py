"""
Provider adapters for ThoughtFlow.

Adapters translate between ThoughtFlow's stable message schema and
provider-specific APIs (OpenAI, Anthropic, local models, etc.).

Example:
    >>> from thoughtflow.adapters import OpenAIAdapter
    >>> adapter = OpenAIAdapter(api_key="...")
    >>> response = adapter.complete(messages, params)
"""

from __future__ import annotations

from thoughtflow.adapters.base import Adapter, AdapterConfig

# Lazy imports to avoid requiring all provider dependencies
# Users only need to install the providers they use

__all__ = [
    "Adapter",
    "AdapterConfig",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "LocalAdapter",
]


def __getattr__(name: str):
    """Lazy load adapters to avoid import errors for missing dependencies."""
    if name == "OpenAIAdapter":
        from thoughtflow.adapters.openai import OpenAIAdapter

        return OpenAIAdapter
    elif name == "AnthropicAdapter":
        from thoughtflow.adapters.anthropic import AnthropicAdapter

        return AnthropicAdapter
    elif name == "LocalAdapter":
        from thoughtflow.adapters.local import LocalAdapter

        return LocalAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

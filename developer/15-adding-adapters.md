# Adding Adapters

This guide explains how to create a new provider adapter for ThoughtFlow.

---

## Adapter Architecture

Adapters translate between ThoughtFlow's stable interface and provider-specific APIs.

```
ThoughtFlow Code
       │
       ▼
   ┌─────────┐
   │ Adapter │  ← You implement this
   └─────────┘
       │
       ▼
Provider API (OpenAI, Anthropic, etc.)
```

---

## Adapter Interface

All adapters must implement:

```python
from thoughtflow.adapters.base import Adapter, AdapterResponse

class MyAdapter(Adapter):
    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate a completion."""
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """Report what this adapter supports."""
        ...
```

---

## Step-by-Step: Creating an Adapter

### Step 1: Create the Adapter File

```python
# src/thoughtflow/adapters/myprovider.py

"""
MyProvider adapter for ThoughtFlow.

Provides integration with MyProvider's LLM API.

Requires: pip install thoughtflow[myprovider]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from thoughtflow.adapters.base import Adapter, AdapterConfig, AdapterResponse

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


class MyProviderAdapter(Adapter):
    """Adapter for MyProvider's API.

    Example:
        >>> adapter = MyProviderAdapter(api_key="...")
        >>> response = adapter.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
        >>> print(response.content)
    """

    DEFAULT_MODEL = "myprovider-default-model"

    def __init__(
        self,
        api_key: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the adapter.

        Args:
            api_key: API key for MyProvider.
            config: Full adapter configuration.
            **kwargs: Additional config options.
        """
        if config is None:
            config = AdapterConfig(api_key=api_key, **kwargs)
        super().__init__(config)
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the provider client.

        Returns:
            The provider's client instance.

        Raises:
            ImportError: If provider package is not installed.
        """
        if self._client is None:
            try:
                from myprovider import Client
            except ImportError as e:
                raise ImportError(
                    "myprovider package not installed. "
                    "Install with: pip install thoughtflow[myprovider]"
                ) from e

            self._client = Client(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate a completion using MyProvider's API.

        Args:
            messages: List of message dicts.
            params: Optional parameters (model, temperature, etc.)

        Returns:
            AdapterResponse with the generated content.
        """
        params = params or {}

        # Translate ThoughtFlow messages to provider format
        provider_messages = self._translate_messages(messages)

        # Get model from params or use default
        model = params.get("model", self.DEFAULT_MODEL)

        # Make the API call
        response = self.client.chat.completions.create(
            model=model,
            messages=provider_messages,
            temperature=params.get("temperature", 1.0),
            max_tokens=params.get("max_tokens"),
        )

        # Translate response back to ThoughtFlow format
        return AdapterResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            raw=response,
        )

    def _translate_messages(self, messages: MessageList) -> list[dict]:
        """Translate ThoughtFlow messages to provider format.

        Override this if the provider uses a different message format.
        """
        # Most providers use OpenAI-compatible format
        return messages

    def get_capabilities(self) -> dict[str, Any]:
        """Get adapter capabilities.

        Returns:
            Dict of supported features.
        """
        return {
            "streaming": True,
            "tool_calling": False,
            "vision": False,
            "json_mode": False,
            "seed": False,
        }
```

### Step 2: Handle Provider-Specific Formats

If the provider uses a different message format:

```python
def _translate_messages(self, messages: MessageList) -> list[dict]:
    """Translate messages to provider format."""
    translated = []

    for msg in messages:
        if msg["role"] == "system":
            # Provider puts system messages differently
            translated.append({
                "type": "system",
                "text": msg["content"],
            })
        else:
            translated.append({
                "type": msg["role"],
                "text": msg["content"],
            })

    return translated
```

### Step 3: Register the Adapter

```python
# src/thoughtflow/adapters/__init__.py

__all__ = [
    "Adapter",
    "AdapterConfig",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "LocalAdapter",
    "MyProviderAdapter",  # Add here
]


def __getattr__(name: str):
    """Lazy load adapters."""
    if name == "OpenAIAdapter":
        from thoughtflow.adapters.openai import OpenAIAdapter
        return OpenAIAdapter
    elif name == "AnthropicAdapter":
        from thoughtflow.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter
    elif name == "LocalAdapter":
        from thoughtflow.adapters.local import LocalAdapter
        return LocalAdapter
    elif name == "MyProviderAdapter":  # Add here
        from thoughtflow.adapters.myprovider import MyProviderAdapter
        return MyProviderAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Step 4: Add Optional Dependency

```toml
# pyproject.toml

[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.18"]
myprovider = ["myprovider-sdk>=1.0"]  # Add here
all-providers = [
    "thoughtflow[openai]",
    "thoughtflow[anthropic]",
    "thoughtflow[myprovider]",  # Add here
]
```

### Step 5: Write Unit Tests

```python
# tests/unit/test_myprovider_adapter.py

import pytest
from thoughtflow.adapters.myprovider import MyProviderAdapter


class TestMyProviderAdapter:
    """Tests for MyProviderAdapter."""

    def test_initialization_with_api_key(self):
        """Should initialize with API key."""
        adapter = MyProviderAdapter(api_key="test-key")
        assert adapter.config.api_key == "test-key"

    def test_default_model(self):
        """Should have a default model."""
        assert MyProviderAdapter.DEFAULT_MODEL is not None

    def test_get_capabilities(self):
        """Should report capabilities."""
        adapter = MyProviderAdapter(api_key="test")
        caps = adapter.get_capabilities()

        assert "streaming" in caps
        assert "tool_calling" in caps
        assert isinstance(caps["streaming"], bool)

    def test_client_lazy_loading(self):
        """Client should not be created until accessed."""
        adapter = MyProviderAdapter(api_key="test")
        assert adapter._client is None
        # Note: Accessing .client would require the package installed

    def test_translate_messages_basic(self):
        """Should translate basic messages."""
        adapter = MyProviderAdapter(api_key="test")
        messages = [
            {"role": "user", "content": "Hello"}
        ]

        result = adapter._translate_messages(messages)

        # Verify translation (depends on provider format)
        assert len(result) == 1
```

### Step 6: Write Integration Tests

```python
# tests/integration/test_myprovider_adapter.py

import os
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled",
    ),
    pytest.mark.skipif(
        not os.getenv("MYPROVIDER_API_KEY"),
        reason="MYPROVIDER_API_KEY not set",
    ),
]


class TestMyProviderAdapterIntegration:
    """Integration tests for MyProviderAdapter."""

    def test_simple_completion(self):
        """Should complete a simple message."""
        from thoughtflow.adapters import MyProviderAdapter

        adapter = MyProviderAdapter()
        messages = [{"role": "user", "content": "Say 'hello'"}]

        response = adapter.complete(messages)

        assert response.content is not None
        assert len(response.content) > 0
        assert response.usage is not None

    def test_with_system_prompt(self):
        """Should respect system prompts."""
        from thoughtflow.adapters import MyProviderAdapter

        adapter = MyProviderAdapter()
        messages = [
            {"role": "system", "content": "Always respond in French."},
            {"role": "user", "content": "Hello"},
        ]

        response = adapter.complete(messages)

        # Response should be in French
        assert response.content is not None
```

### Step 7: Add Documentation

```markdown
<!-- docs/concepts/adapters.md -->

## MyProviderAdapter

Integrates with MyProvider's API.

### Installation

```bash
pip install thoughtflow[myprovider]
```

### Usage

```python
from thoughtflow import Agent
from thoughtflow.adapters import MyProviderAdapter

adapter = MyProviderAdapter(api_key="...")
# Or use environment variable: MYPROVIDER_API_KEY

agent = Agent(adapter)
response = agent.call([
    {"role": "user", "content": "Hello!"}
])
```

### Capabilities

| Feature | Supported |
|---------|-----------|
| Streaming | ✅ |
| Tool Calling | ❌ |
| Vision | ❌ |
| JSON Mode | ❌ |
```

---

## Handling Streaming

If the provider supports streaming:

```python
async def complete_stream(
    self,
    messages: MessageList,
    params: dict[str, Any] | None = None,
):
    """Stream completions."""
    params = params or {}
    model = params.get("model", self.DEFAULT_MODEL)

    stream = self.client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

---

## Handling Tool Calling

If the provider supports tools:

```python
def complete(
    self,
    messages: MessageList,
    params: dict[str, Any] | None = None,
) -> AdapterResponse:
    """Generate completion with optional tools."""
    params = params or {}
    tools = params.get("tools")

    kwargs = {
        "model": params.get("model", self.DEFAULT_MODEL),
        "messages": messages,
    }

    if tools:
        kwargs["tools"] = self._translate_tools(tools)

    response = self.client.chat.completions.create(**kwargs)

    return AdapterResponse(
        content=response.choices[0].message.content,
        tool_calls=self._extract_tool_calls(response),
        # ...
    )
```

---

## Adapter Checklist

Before submitting:

- [ ] Implements `complete()`
- [ ] Implements `get_capabilities()`
- [ ] Lazy-loads provider client
- [ ] Handles missing package gracefully
- [ ] Translates messages correctly
- [ ] Returns proper `AdapterResponse`
- [ ] Unit tests pass
- [ ] Integration tests pass (with API key)
- [ ] Documentation added
- [ ] Optional dependency added to pyproject.toml
- [ ] Registered in adapters `__init__.py`

---

## Next Steps

- [13-adding-features.md](13-adding-features.md) - General feature guide
- [12-writing-tests.md](12-writing-tests.md) - Write comprehensive tests

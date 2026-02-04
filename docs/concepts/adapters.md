# Adapters

Adapters translate between ThoughtFlow's stable message schema and provider-specific APIs.

---

## Available Adapters

| Adapter | Provider | Install |
|---------|----------|---------|
| `OpenAIAdapter` | OpenAI (GPT-4, etc.) | `pip install thoughtflow[openai]` |
| `AnthropicAdapter` | Anthropic (Claude) | `pip install thoughtflow[anthropic]` |
| `LocalAdapter` | Ollama, LM Studio | `pip install thoughtflow[local]` |

---

## Basic Usage

```python
from thoughtflow.adapters import OpenAIAdapter

# With explicit API key
adapter = OpenAIAdapter(api_key="sk-...")

# Or from environment variable (OPENAI_API_KEY)
adapter = OpenAIAdapter()

# Call directly
response = adapter.complete([
    {"role": "user", "content": "Hello!"}
])
print(response.content)
```

---

## Adapter Configuration

All adapters accept an `AdapterConfig`:

```python
from thoughtflow.adapters.base import AdapterConfig

config = AdapterConfig(
    api_key="sk-...",
    base_url="https://custom-endpoint.com/v1",
    timeout=120.0,
    max_retries=5,
    default_model="gpt-4",
)

adapter = OpenAIAdapter(config=config)
```

---

## Adapter Response

All adapters return an `AdapterResponse`:

```python
response = adapter.complete(messages)

print(response.content)      # The generated text
print(response.model)        # Model that generated it
print(response.usage)        # Token usage dict
print(response.finish_reason)  # Why it stopped
print(response.raw)          # Raw provider response
```

---

## Capabilities

Check what an adapter supports:

```python
caps = adapter.get_capabilities()

print(caps["streaming"])     # Supports streaming?
print(caps["tool_calling"])  # Supports tools?
print(caps["vision"])        # Supports images?
print(caps["json_mode"])     # Supports JSON mode?
```

---

## Creating Custom Adapters

Implement the `Adapter` interface:

```python
from thoughtflow.adapters.base import Adapter, AdapterResponse

class MyCustomAdapter(Adapter):
    def complete(self, messages, params=None):
        # Your implementation here
        return AdapterResponse(
            content="Response text",
            model="my-model",
            usage={"total_tokens": 10},
        )
```

---

## Design Philosophy

- **Clean boundaries**: Adapters handle ALL provider differences
- **Lazy loading**: Provider SDKs only imported when used
- **Optional extras**: Only install what you need
- **Explicit capabilities**: Know what each adapter supports

# LLM

> The multi-provider interface for calling language model services — the mouth of the framework.

## Philosophy

Every cognitive primitive in ThoughtFlow that needs to talk to a language model goes through LLM. It exists to unify the fragmented landscape of model providers behind a single, consistent interface. Instead of wiring your THOUGHTs, AGENTs, or CHAT flows to OpenAI-specific code, Anthropic-specific code, or local Ollama code, you wire them to LLM. Swap providers by changing a string; the rest of your system stays unchanged.

LLM is deliberately minimal. It uses only the Python standard library (urllib, json) — zero external dependencies. A unified param pipeline (`merge_call_params` + `split_call_params`) ensures model knobs reach the wire cleanly while transport keys stay in headers and URLs. Prompt caching is first-class via `cache=True` on messages.

## How It Works

LLM parses a `service:model` identifier and routes calls to `_call_*` provider methods. Each method receives pre-split wire params (model knobs) and transport context (base_url, referer, extra_headers). Messages flow through `_prepare_messages_for_provider()` which normalizes structure, maps roles, and applies cache wire adapters.

After every call: `last_params` (full merge), `last_error` (transport/API failure), `last_usage` (normalized token + cache fields). Optional `on_usage(record)` callback for metering.

Record/replay exchange keys use messages with cache markers stripped — semantic content hashes stay stable.

## Inputs & Configuration

### Constructor

| Parameter | Description |
|-----------|-------------|
| `model_id` | `service:model` format |
| `key` | API key |
| `secret` | Optional API secret |
| `request_timeout` | Opt-in socket timeout in seconds (default None = blocking) |
| `on_usage` | Optional callback `fn(record)` after successful calls with usage |
| `record` | Optional MEMORY to record exchanges into |
| `**kwargs` | Default model + transport params (see buckets below) |

### Param buckets

| Bucket | Examples | `default_params`? | On wire? |
|--------|----------|-------------------|----------|
| Reserved | `request_timeout`, `on_usage`, `record` | No | No |
| Transport | `base_url`, `extra_headers`, `referer`, `title`, `ollama_url` | Yes | No |
| Model | `temperature`, `max_tokens`, `reasoning_effort`, `prompt_cache_key` | Yes | Yes |

### Common model parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `temperature` | float | Sampling randomness |
| `max_tokens` | int | Response token budget |
| `top_p` | float | Nucleus sampling |
| `frequency_penalty` | float | Repetition penalty (OpenAI-compat) |
| `presence_penalty` | float | Presence penalty (OpenAI-compat) |
| `reasoning_effort` | str | gpt-oss / GLM reasoning depth |
| `reasoning_format` | str | Groq Qwen think visibility (`hidden` recommended) |
| `prompt_cache_key` | str | OpenAI-compatible cache namespace |

### Prompt caching

| Helper | Description |
|--------|-------------|
| `cached_system(text)` | System message with `cache=True` |
| `cached_message(role, content)` | Any role with `cache=True` |

Anthropic: transforms to `cache_control: {type: ephemeral}`. OpenAI-compatible: prefix caching + optional `prompt_cache_key`. Ollama/Gemini: markers stripped (no-op).

### Instance state after `.call()`

| Attribute | Description |
|-----------|-------------|
| `last_params` | Full merged default + per-call params |
| `last_error` | str or None — API/transport failure |
| `last_usage` | Normalized usage dict or None |

### Native provider classes

| Class | Module | Defaults |
|-------|--------|----------|
| `GroqLLM` | `thoughtflow.providers` | Qwen `reasoning_format=hidden` |
| `CerebrasLLM` | `thoughtflow.providers` | User-Agent, optional key fallback |
| `OpenRouterLLM` | `thoughtflow.providers` | Referer + Title headers |

## Usage

```python
from thoughtflow import LLM, cached_system, GroqLLM

llm = LLM(
    model_id="openai:gpt-4o",
    key="OPENAI_API_KEY",
    temperature=0.7,
    request_timeout=90,
)

choices = llm.call([
    cached_system("Long stable system prompt."),
    {"role": "user", "content": "Plan the next step."},
])

if llm.last_error:
    raise RuntimeError(llm.last_error)
print(llm.last_usage)
```

```python
# Production tier — Groq Qwen with safe defaults
llm = GroqLLM("qwen/qwen3-32b", key=GROQ_KEY, max_tokens=12000, reasoning_effort="low")
```

```python
# Cerebras — Cloudflare-safe
from thoughtflow import CerebrasLLM

llm = CerebrasLLM("gpt-oss-120b", key=CEREBRAS_KEY, reasoning_effort="low")
```

## Relationship to Other Primitives

LLM is consumed by THOUGHT, AGENT, and CHAT. EMBED mirrors the record/replay seam. See `docs/concepts/llm.md` for the concept guide.

## Considerations for Future Development

- Streaming for Anthropic and Gemini native SSE
- Gemini context cache API (separate from message cache markers)
- OpenAI Responses API (`OpenAIResponsesLLM`) — deferred

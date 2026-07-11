# LLM

LLM is the single interface to every language model provider. One class, one `call()` method, zero dependencies — every provider is reached through Python's standard library.

There is nothing to install or configure per provider. The provider is part of the model string.

---

## The service:model Format

An LLM is identified by a single string: `"service:model"`.

```python
from thoughtflow import LLM

llm = LLM("openai:gpt-4o", key="sk-...")

response = llm.call([
    {"role": "user", "content": "Hello!"}
])
print(response[0])
```

`call()` always returns a `list[str]` — one string per choice. Most of the time you want `response[0]`.

### Supported Providers

| Service | Example |
|---------|---------|
| `openai` | `LLM("openai:gpt-4o", key=...)` |
| `anthropic` | `LLM("anthropic:claude-3-5-sonnet-20241022", key=...)` |
| `groq` | `LLM("groq:llama-3.1-70b-versatile", key=...)` |
| `gemini` | `LLM("gemini:gemini-1.5-pro", key=...)` |
| `openrouter` | `LLM("openrouter:meta-llama/llama-3.1-70b-instruct", key=...)` |
| `ollama` | `LLM("ollama:llama3.2")` — local, no key needed |

### Native convenience classes (optional)

Production harnesses may prefer thin subclasses with safe defaults. All inherit the same param and caching pipeline as `LLM`:

```python
from thoughtflow import GroqLLM, CerebrasLLM, OpenRouterLLM

groq = GroqLLM("qwen/qwen3-32b", key=...)       # reasoning_format=hidden for Qwen
cerebras = CerebrasLLM("gpt-oss-120b", key=...)  # Cloudflare-safe User-Agent
router = OpenRouterLLM("anthropic/claude-3.5-sonnet", key=...)  # Referer + Title headers
```

Switching providers is a one-line change. Everything built on top of the LLM — THOUGHT, AGENT, WORKFLOW — stays the same.

---

## Parameters and Defaults

Constructor kwargs become defaults applied to every call. Per-call `params` override them. The merged result is always available on `last_params`.

### Param buckets

| Bucket | Examples | Sent on wire? | In replay key? |
|--------|----------|---------------|----------------|
| **Model** | `temperature`, `max_tokens`, `reasoning_effort`, `prompt_cache_key` | Yes | Yes |
| **Transport** | `base_url`, `extra_headers`, `referer`, `title`, `ollama_url` | No (headers/URL only) | No |
| **Reserved** | `request_timeout`, `on_usage`, `record` | No | No |

```python
llm = LLM(
    "openai:gpt-4o",
    key="sk-...",
    temperature=0.7,
    max_tokens=1024,
    request_timeout=90,  # opt-in socket timeout (seconds)
)

response = llm.call(messages)
response = llm.call(messages, params={"temperature": 0.1})  # override one knob
```

### Param spectrum

| Family | Keys | Notes |
|--------|------|-------|
| Sampling | `temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, `seed` | May be ignored when reasoning mode is active on some models |
| Budget | `max_tokens` | Mapped to `generationConfig` on Gemini |
| Reasoning | `reasoning_effort`, `reasoning_format` | Pass-through on OpenAI-compatible hosts; use `GroqLLM` for Qwen |
| Cache namespace | `prompt_cache_key` | OpenAI-compatible optional wire param |

OpenAI-compatible services (`openai`, `groq`, `openrouter`, `OpenAICompatibleLLM`, `CerebrasLLM`) pass unknown kwargs through to the API body — tier dicts keep working without ThoughtFlow enumerating every knob.

---

## Prompt caching

Modern agentic loops resend the same system prompt every turn. Provider prompt caching cuts latency and cost. Mark stable prefixes explicitly:

```python
from thoughtflow import LLM, cached_system

SYSTEM = cached_system("You are a planner. ... thousand tokens ...")

llm = LLM("anthropic:claude-3-5-sonnet", key=..., temperature=0)
llm.call([SYSTEM, {"role": "user", "content": user_turn}])

# Inspect cache hits on the instance after each call
print(llm.last_usage.get("cache_read_input_tokens"))
```

| Mechanism | What it caches |
|-----------|----------------|
| **Provider prompt cache** | Input token prefixes at the API (live production) |
| **LLM.record / replay** | Full request→response exchanges in MEMORY (tests, CI) |

Cache markers (`cache=True`) are stripped from replay exchange keys — recordings stay stable whether or not caching was enabled during record. Model params like `temperature` still affect replay keys.

Anthropic: `cache=True` becomes `cache_control: {type: ephemeral}` on content blocks. OpenAI-compatible: automatic prefix caching on supported models; optional `prompt_cache_key` in params.

---

## Error and usage visibility

After every call, inspect the LLM instance:

```python
if llm.last_error:
    print("transport failure:", llm.last_error)
else:
    print("usage:", llm.last_usage)
```

`last_usage` normalizes token counts plus cache fields (`cached_tokens`, `cache_read_input_tokens`, `reasoning_tokens`) across providers.

Optional metering hook:

```python
def meter(record):
    log_tokens(record["prompt_tokens"], record.get("cached_tokens", 0))

llm = LLM("openai:gpt-4o", key=..., on_usage=meter)
```

When the API returns an error dict instead of choices, `last_error` is set — distinguish transport failure from an empty model response (also check `last_error` when choices look empty).

---

## Structured Output

Pass a JSON Schema via `output_schema` and the model is constrained to return conforming JSON:

```python
import json

schema = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "temperature_c": {"type": "number"},
    },
    "required": ["city", "temperature_c"],
    "additionalProperties": False,
}

response = llm.call(messages, output_schema=schema)
data = json.loads(response[0])
```

Each provider's native mechanism is used where one exists: `response_format` for OpenAI, Groq, and OpenRouter; tool-use wrapping for Anthropic; the `format` key for Ollama. Providers without native support fall back to prompt injection.

---

## Streaming

Pass `stream=True` to get a generator of text chunks instead of a complete response:

```python
for chunk in llm.call(messages, stream=True):
    print(chunk, end="", flush=True)
```

OpenAI, Groq, OpenRouter, and Ollama stream natively. Anthropic and Gemini currently fall back to a single-yield non-streaming call, so the same code works everywhere.

---

## Role Mapping

ThoughtFlow uses a small set of internal message roles. Beyond the familiar `user`/`assistant`/`system`, the agent loop records tool interactions with `action` (the tool request) and `result` (the tool output). Providers do not accept these strings directly, so the LLM translates them at the API boundary using `PROVIDER_ROLE_MAP`:

- `action`/`result` become `tool` for OpenAI-style APIs and `assistant` for Anthropic.
- Gemini maps `action`/`result`/`assistant` to `model` and `system` to `user`.

Your code and your MEMORY always use ThoughtFlow roles; translation is a transport detail. Roles without a mapping pass through unchanged — if a provider rejects one, you get the provider's error rather than a silent rewrite.

---

## Local Models

Three ways to run against local or self-hosted models:

```python
# 1. Ollama (http://localhost:11434 by default)
llm = LLM("ollama:llama3.2")
llm = LLM("ollama:llama3.2", ollama_url="http://192.168.1.10:11434")

# 2. Any OpenAI-compatible server, via base_url
llm = LLM("openai:my-model", key="dummy", base_url="http://127.0.0.1:8000/v1")

# 3. The convenience class for the same thing
from thoughtflow import OpenAICompatibleLLM

llm = OpenAICompatibleLLM(
    model="mlx-community/Llama-3-8B-Instruct",
    base_url="http://127.0.0.1:8765/v1",
)
```

`base_url` works with vLLM, llama.cpp, LM Studio, MLX, and anything else that speaks the OpenAI chat completions protocol. Use `extra_headers` to add custom headers (e.g. for a proxy in front of the server).

---

## Record and Replay

Every LLM can record its exchanges into a MEMORY and later replay them deterministically — offline, instant, byte-identical:

```python
llm = LLM("openai:gpt-4o", key="sk-...").record(memory)
# ... run your flow; every exchange is captured as MEMORY events ...
memory.to_json("session.json")

# Later: no network, no API key
replay_llm = LLM.replay(MEMORY.from_json("session.json"))
```

This is the foundation of deterministic testing in ThoughtFlow. Provider prompt caching and replay are orthogonal — see [Deterministic Replay](replay.md).

---

## Design Philosophy

- **One string, one class**: the provider lives in the model ID, not in your architecture
- **Stdlib only**: every provider is reached with `urllib` — nothing to install
- **Roles are stable**: ThoughtFlow roles in your code; provider translation at the boundary
- **Recordable**: any LLM becomes a deterministic test fixture
- **Params pass through**: tier dicts forward provider knobs without a central enum
- **Cache when stable**: opt-in `cache=True` on messages; no magic auto-cache

For the complete API reference, see [primitives/LLM.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/LLM.md).

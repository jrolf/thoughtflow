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

Switching providers is a one-line change. Everything built on top of the LLM — THOUGHT, AGENT, WORKFLOW — stays the same.

---

## Parameters and Defaults

Constructor kwargs become defaults applied to every call. Per-call `params` override them.

```python
llm = LLM(
    "openai:gpt-4o",
    key="sk-...",
    temperature=0.7,
    max_tokens=1024,
)

# Uses the defaults
response = llm.call(messages)

# Overrides temperature for this call only
response = llm.call(messages, params={"temperature": 0.1})
```

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

This is the foundation of deterministic testing in ThoughtFlow. See [Deterministic Replay](replay.md) for the full story.

---

## Design Philosophy

- **One string, one class**: the provider lives in the model ID, not in your architecture
- **Stdlib only**: every provider is reached with `urllib` — nothing to install
- **Roles are stable**: ThoughtFlow roles in your code; provider translation at the boundary
- **Recordable**: any LLM becomes a deterministic test fixture

For the complete API reference, see [primitives/LLM.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/LLM.md).

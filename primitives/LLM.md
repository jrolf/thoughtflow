# LLM

> The multi-provider interface for calling language model services — the mouth of the framework.

## Philosophy

Every cognitive primitive in ThoughtFlow that needs to talk to a language model goes through LLM. It exists to unify the fragmented landscape of model providers behind a single, consistent interface. Instead of wiring your THOUGHTs, AGENTs, or CHAT flows to OpenAI-specific code, Anthropic-specific code, or local Ollama code, you wire them to LLM. Swap providers by changing a string; the rest of your system stays unchanged.

LLM is deliberately minimal. It uses only the Python standard library (urllib, json) — zero external dependencies. This keeps ThoughtFlow deployable in constrained environments like AWS Lambda and ensures that the framework remains portable. The design favors clarity and consistency over provider-specific optimizations. When you need structured output or streaming, those capabilities are built in; when you need a new provider, the pattern is clear.

## How It Works

LLM parses a `service:model` identifier (e.g., `openai:gpt-4o`, `anthropic:claude-3-5-sonnet`) and routes calls to the matching provider method (`_call_openai`, `_call_anthropic`, etc.). Each provider method constructs the HTTP request in the provider's expected format, sends it via urllib, and parses the response. The result is always a list of strings — one per completion choice — so downstream code has a predictable shape to work with.

Messages are normalized before sending. You can pass plain strings, dicts with `role` and `content`, or mixed formats; `_normalize_messages()` converts everything to the canonical `{role, content}` structure that providers expect. For structured output, you pass an `output_schema` dict; the LLM uses the provider's native mechanism (OpenAI's `response_format`, Anthropic's tool-use pattern, etc.) to constrain the model's output. When `stream=True`, the LLM yields token chunks as they arrive instead of buffering the full response.

The last merged parameters used for each call are stored in `last_params` for debugging and inspection. Default parameters are stored in `default_params`.

LLM is also the seam for ThoughtFlow's record/replay system. `llm.record(memory)` captures every subsequent exchange (request + response, keyed by a content hash) as events in the given MEMORY. `LLM.replay(memory)` returns a `ReplayLLM` — a drop-in LLM that serves those recorded responses deterministically, with no network and no keys. Unrecorded requests raise `ReplayMissError`, or fall back to a live LLM passed via `on_miss=`. The exchange key is computed from the normalized messages, content params (transport-only keys like `base_url` are excluded), the output schema, and the service/model identity — so recordings survive endpoint changes and JSON round-trips.

For local and self-hosted models, pass `base_url` to target any OpenAI-compatible server (vLLM, LM Studio, llama.cpp, MLX), or use the `OpenAICompatibleLLM` convenience subclass. Ollama is a first-class service with its own provider method.

## Inputs & Configuration

### Constructor

| Parameter | Description |
|-----------|-------------|
| `model_id` | String in `service:model` format (e.g., `openai:gpt-4o`, `anthropic:claude-3-5-sonnet`, `ollama:llama3`) |
| `key` | API key for the provider (env var name or actual key) |
| `secret` | Optional API secret for providers that require it |
| `**kwargs` | Default call parameters — applied to every `.call()` unless overridden (see table below) |

### Default Parameters (constructor kwargs)

These are the five most commonly used parameters. Any provider-specific key is also accepted.

| Parameter | Type | Description |
|-----------|------|-------------|
| `temperature` | float 0–2 | Controls randomness. Lower = more focused; higher = more creative. |
| `max_tokens` | int | Maximum number of tokens in the response. |
| `top_p` | float 0–1 | Nucleus sampling threshold. Controls diversity via probability mass. |
| `frequency_penalty` | float -2–2 | Reduces repetition of tokens that have already appeared frequently. |
| `presence_penalty` | float -2–2 | Reduces repetition of any token that has appeared at all. |

### `.call()` arguments

| Parameter | Description |
|-----------|-------------|
| `msg_list` | List of messages — strings or dicts with `role` and `content` |
| `params` | Per-call parameters — merged with defaults; per-call values win on conflict |
| `output_schema` | Optional JSON Schema dict for structured output enforcement |
| `stream` | If True, returns a generator yielding token chunks instead of full response |

**Supported providers:** OpenAI, Anthropic, Groq, Ollama (local), Gemini, OpenRouter.

## Usage

```python
from thoughtflow import LLM

# --- Basic call with per-call params ---
llm = LLM(model_id='openai:gpt-4o', key='OPENAI_API_KEY')
choices = llm.call([
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': 'Summarize this in one sentence.'}
], params={'temperature': 0.7})
response = choices[0]
```

```python
# --- Constructor defaults: set once, applied to every call ---
llm = LLM(
    model_id='openai:gpt-4o',
    key='OPENAI_API_KEY',
    temperature=0.7,
    max_tokens=1024,
    top_p=0.95,
)

# Uses temperature=0.7, max_tokens=1024, top_p=0.95 automatically
choices = llm.call([{'role': 'user', 'content': 'Tell me a joke.'}])

# Override just one value; defaults still apply for the rest
choices = llm.call([{'role': 'user', 'content': 'Be precise.'}], params={'temperature': 0.1})
```

```python
# --- Structured output ---
schema = {'name': 'extract', 'properties': {'summary': {'type': 'string'}}, 'required': ['summary']}
choices = llm.call(msgs, output_schema=schema)

# --- Streaming ---
for chunk in llm.call(msgs, stream=True):
    print(chunk, end='')
```

```python
# --- Record & replay (deterministic testing) ---
from thoughtflow import LLM, MEMORY

recording = MEMORY()
llm.record(recording)            # capture every exchange as events
# ... run your flow ...
recording.to_json('session.json')

replay_llm = LLM.replay(MEMORY.from_json('session.json'))
# replay_llm is call-compatible: same flow, no network, identical outputs
```

```python
# --- Local OpenAI-compatible servers ---
from thoughtflow import OpenAICompatibleLLM

llm = OpenAICompatibleLLM(model='my-model', base_url='http://localhost:8000/v1')
# Equivalent to: LLM('openai:my-model', key='dummy', base_url='http://localhost:8000/v1')
```

## Relationship to Other Primitives

LLM is consumed by THOUGHT (which uses it for llm_call operations), AGENT (which uses it in the agentic loop), and CHAT (which uses it for turn-by-turn conversation). When recording, LLM writes exchange events into a MEMORY via `add_exchange()`; `ReplayLLM` reads them back via `get_exchanges()`. EMBED is its sibling — the embedding counterpart for vector operations, with the identical record/replay seam. TOOL schemas and LLM structured output share the same JSON Schema format, so they integrate cleanly.

## Considerations for Future Development

- Add streaming support for Anthropic and Gemini (currently fall back to single-yield)
- Consider async variants for high-throughput or concurrent use cases
- Provider-specific extensions (e.g., vision, function calling) may warrant optional hooks
- Caching layer for repeated prompts could reduce latency and cost in development

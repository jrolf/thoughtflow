# LLM

> The multi-provider interface for calling language model services — the mouth of the framework.

## Philosophy

Every cognitive primitive in ThoughtFlow that needs to talk to a language model goes through LLM. It exists to unify the fragmented landscape of model providers behind a single, consistent interface. Instead of wiring your THOUGHTs, AGENTs, or CHAT flows to OpenAI-specific code, Anthropic-specific code, or local Ollama code, you wire them to LLM. Swap providers by changing a string; the rest of your system stays unchanged.

LLM is deliberately minimal. It uses only the Python standard library (urllib, json) — zero external dependencies. This keeps ThoughtFlow deployable in constrained environments like AWS Lambda and ensures that the framework remains portable. The design favors clarity and consistency over provider-specific optimizations. When you need structured output or streaming, those capabilities are built in; when you need a new provider, the pattern is clear.

## How It Works

LLM parses a `service:model` identifier (e.g., `openai:gpt-4o`, `anthropic:claude-3-5-sonnet`) and routes calls to the appropriate provider adapter. Each adapter constructs the HTTP request in the provider's expected format, sends it via urllib, and parses the response. The result is always a list of strings — one per completion choice — so downstream code has a predictable shape to work with.

Messages are normalized before sending. You can pass plain strings, dicts with `role` and `content`, or mixed formats; `_normalize_messages()` converts everything to the canonical `{role, content}` structure that providers expect. For structured output, you pass an `output_schema` dict; the LLM uses the provider's native mechanism (OpenAI's `response_format`, Anthropic's tool-use pattern, etc.) to constrain the model's output. When `stream=True`, the LLM yields token chunks as they arrive instead of buffering the full response.

The last parameters used for each call are stored in `last_params` for debugging and inspection.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| model_id | String in `service:model` format (e.g., `openai:gpt-4o`, `anthropic:claude-3-5-sonnet`, `ollama:llama3`) |
| key | API key for the provider (env var name or actual key) |
| secret | Optional API secret for providers that require it |
| msg_list | List of messages — strings or dicts with `role` and `content` |
| params | Provider-specific parameters (temperature, max_tokens, etc.) |
| output_schema | Optional JSON Schema dict for structured output enforcement |
| stream | If True, returns a generator yielding token chunks instead of full response |

**Supported providers:** OpenAI, Anthropic, Groq, Ollama (local), Gemini, OpenRouter.

## Usage

```python
from thoughtflow import LLM

llm = LLM(model_id='openai:gpt-4o', key='OPENAI_API_KEY')
choices = llm.call([
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': 'Summarize this in one sentence.'}
], params={'temperature': 0.7})
response = choices[0]
```

```python
# Structured output
schema = {'name': 'extract', 'properties': {'summary': {'type': 'string'}}, 'required': ['summary']}
choices = llm.call(msgs, output_schema=schema)

# Streaming
for chunk in llm.call(msgs, stream=True):
    print(chunk, end='')
```

## Relationship to Other Primitives

LLM is consumed by THOUGHT (which uses it for llm_call operations), AGENT (which uses it in the agentic loop), and CHAT (which uses it for turn-by-turn conversation). It does not depend on MEMORY or any other primitive. EMBED is its sibling — the embedding counterpart for vector operations. TOOL schemas and LLM structured output share the same JSON Schema format, so they integrate cleanly.

## Considerations for Future Development

- Add streaming support for Anthropic and Gemini (currently fall back to single-yield)
- Consider async variants for high-throughput or concurrent use cases
- Provider-specific extensions (e.g., vision, function calling) may warrant optional adapter hooks
- Caching layer for repeated prompts could reduce latency and cost in development

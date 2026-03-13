# EMBED

> Multi-provider interface for text embedding APIs.

## Philosophy

EMBED exists because embedding endpoints are fundamentally different from chat completion endpoints. LLM handles text generation: you send messages, you get a completion. EMBED handles vectorization: you send text, you get a list of floats. Conflating them would muddy the interface and force users to remember which methods apply to which mode. Keeping them separate preserves the principle that each primitive has one clear job.

EMBED mirrors LLM's architecture deliberately. Both use the same `service:model` format (e.g., `openai:text-embedding-3-small`, `ollama:nomic-embed-text`), the same credential pattern, and the same provider-routing logic. This consistency reduces cognitive load: if you know how to use LLM, you already understand EMBED's shape. It is a low-level building block that higher-level code (semantic memory, retrieval, similarity-based routing) can compose with freely.

## How It Works

EMBED parses the model_id into a service prefix and model suffix. On `call(text, params)`, it detects whether the input is a single string or a list of strings. Single strings are wrapped into a one-element list internally; after the provider returns, the single result is unwrapped so the caller receives a flat vector. List input returns a list of vectors.

Provider routing is by service prefix. OpenAI, Groq, and OpenRouter share the same response format: `{"data": [{"embedding": [...], "index": 0}, ...], "usage": {...}}`. EMBED sorts by index to guarantee output order matches input order. Ollama uses `/api/embed` and returns `{"embeddings": [[...], ...]}`. Gemini uses `batchEmbedContents` with a `task_type` parameter (e.g., RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY). Metadata (prompt_tokens, total_tokens, model, or Ollama-specific durations) is captured in `last_meta` after each call.

All HTTP is done via `urllib`; no third-party dependencies.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| model_id | Provider and model in `service:model` format. Defaults to `openai:text-embedding-3-small` if no colon present. |
| key | API key for the provider. |
| secret | Optional API secret for additional authentication. |

**Supported services:** OpenAI, Groq, Ollama, Gemini, OpenRouter.

**call() parameters:**

| Parameter | Description |
|-----------|-------------|
| text | Single string or list of strings to embed. |
| params | Optional dict. Supports `dimensions` (text-embedding-3-*), `encoding_format`, `task_type` (Gemini), `ollama_url` (Ollama), `referer`/`title` (OpenRouter). |

## Usage

```python
from thoughtflow import EMBED

# Single string returns a flat vector
embed = EMBED("openai:text-embedding-3-small", key="sk-...")
vector = embed.call("Hello world")
# vector is list of floats, e.g. len 1536

# List returns list of vectors
vectors = embed.call(["Hello", "World"])
# len(vectors) == 2

# Local Ollama
embed = EMBED("ollama:nomic-embed-text")
vector = embed.call("Local embedding")

# Truncated dimensions (text-embedding-3-*)
vector = embed.call("Short vector", params={"dimensions": 256})
```

## Relationship to Other Primitives

EMBED is a sibling to LLM. It does not depend on MEMORY, THOUGHT, or ACTION. Higher-level primitives (semantic memory, retrieval layers, similarity routing) can use EMBED as a building block. AGENT and WORKFLOW may eventually consume embeddings for context selection or RAG, but EMBED itself remains a standalone primitive.

## Considerations for Future Development

- Add support for additional providers (Anthropic embeddings, Cohere, etc.) as they become relevant.
- Consider batch size limits and chunking for very large input lists.
- Expose `last_meta` more formally (e.g., as a structured result object) for observability.
- Evaluate async variants if embedding calls become a latency bottleneck in agent loops.

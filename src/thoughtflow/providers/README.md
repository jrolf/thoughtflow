# `src/thoughtflow/providers/` — Native Provider Convenience Subclasses

> **Scope:** Thin, zero-dependency `LLM` subclasses encoding production-hardened defaults for specific inference gateways.
> **Base class:** [`LLM`](../llm.py) · **Concept guide:** [`docs/concepts/llm.md`](../../../docs/concepts/llm.md)

---

## Why These Classes Exist

`LLM("service:model", key=...)` is — and remains — the canonical entry point for every language model in ThoughtFlow. However, running high-volume multi-provider agent fleets in production surfaces recurring provider-specific footguns:

- **Cloudflare HTTP 1010 blocks** when Python's default `Python-urllib/3.x` `User-Agent` hits certain inference edges (e.g. Cerebras).
- **Unstripped `<think>...</think>` chain-of-thought blocks** hijacking downstream JSON/schema parsers on reasoning-enabled open-weight models (e.g. Qwen3 on Groq).
- **Gateway attribution headers** (`HTTP-Referer`, `X-Title`) expected on every OpenRouter call without leaking those keys into JSON request bodies.

Rather than forcing every downstream project to rediscover and copy-paste those transport workarounds, `providers/` packages them as optional convenience subclasses.

---

## Architectural Rules

Every class in this directory obeys three strict rules:
1. **Zero duplicate wire logic:** Subclasses inherit `LLM.call()`, `LLM.chat()`, `merge_call_params()`, `split_call_params()`, prompt caching (`cached_system`), and `record()`/`replay()` directly from `LLM`.
2. **Caller overrides always win:** Defaults are applied via `setdefault` (or fallback hooks), never overriding explicit per-call or constructor kwargs.
3. **Pure stdlib:** No vendor SDKs (`groq`, `openai`, `cerebras-cloud-sdk`) are ever imported.

---

## Available Classes

| Module | Class | Exported At | Production Defaults Added |
|--------|-------|-------------|---------------------------|
| `groq.py` | `GroqLLM` | `thoughtflow.GroqLLM` | Sets `reasoning_format="hidden"` by default when `model` is a Qwen slug (`qwen/...`), plus defensive `<think>...</think>` stripping if `strip_think_tags=True` |
| `cerebras.py` | `CerebrasLLM` | `thoughtflow.CerebrasLLM` | Routes via `OpenAICompatibleLLM` (`https://api.cerebras.ai/v1`) with a Cloudflare-safe `User-Agent` header and optional `CEREBRAS_API_KEY` env fallback on `401`/`403` |
| `openrouter.py` | `OpenRouterLLM` | `thoughtflow.OpenRouterLLM` | Sets default `referer` (`HTTP-Referer`) and `title` (`X-Title`) transport params, stripped cleanly before JSON serialization by `split_call_params()` |

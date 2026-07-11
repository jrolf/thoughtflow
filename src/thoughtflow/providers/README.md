# providers/

Native provider convenience classes for production LLM tier maps.

These thin subclasses inherit the unified param pipeline (`llm_params.split_call_params`) and prompt caching adapters (`llm_cache`) from the base `LLM` class. They only add safe defaults via `setdefault` — they do not reimplement wire logic.

| Module | Class | Purpose |
|--------|-------|---------|
| `groq.py` | `GroqLLM` | Qwen `reasoning_format=hidden` default; optional think-block strip |
| `cerebras.py` | `CerebrasLLM` | Cloudflare-safe `User-Agent`; optional auth key fallback |
| `openrouter.py` | `OpenRouterLLM` | `HTTP-Referer` and `X-Title` attribution defaults |

`LLM(model_id="groq:...")` remains the canonical entry point. Native classes are optional shortcuts.

See `docs/concepts/llm.md` and `.PLANS/PROVIDER_INTEGRATION_RESPONSE_PLAN.md`.

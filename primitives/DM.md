# DM

> Multi-provider interface for structured System-One decision models.

## Philosophy

`DM` exists because decision models are a distinct intelligence primitive alongside `LLM` and `EMBED`. Where `LLM` sends messages to a generative chat endpoint and returns text, and `EMBED` sends text to an embedding endpoint and returns a vector, `DM` sends structured `state` plus one or more typed `questions` (`choice`, `noul`, `score`, `box`) and returns calibrated probability distributions in a single forward pass without prose generation.

Passing a decision model such as `typesafe/jev-1.14` to a `/chat/completions` endpoint fails at the API layer (`400 Bad Request`). Conversely, forcing decision-model callers to hand-write per-vendor JSON envelopes would leak wire dialects into application logic. `DM` absorbs those wire differences behind the exact same `service:model`, credential, parameter, `on_usage`, and `record`/`replay` contract used by `LLM` and `EMBED`.

## How It Works

`DM` parses `model_id` into `(service, model)` (defaulting bare slugs such as `"typesafe/jev-1.14"` to `"openrouter:typesafe/jev-1.14"`). On `call(state, questions, params)`, `DM`:

1. **Normalizes `questions`** from ergonomic Python shorthands (`choices=["a", "b"]`, `choices={"a": "desc"}`, `levels=["Low", "Med", "High"]`, `type="noul"` / `"predicate"` / `"bool"`) into a canonical internal map.
2. **Encodes the target provider's wire dialect**:
   - **`systemone`**: OpenRouter (`/api/alpha/decisions` and `/api/v1/systemone`), TypeSafe (`/v1/systemone`, adding `TypeSafe-Danger-Zone-Images: true` automatically when `assets` or `box` is used), Liquid (`/decisions/v1/systemone`), Perplexity (`/v1/decisions`), Inception (`/v1/decisions`), Upstage (`/v1/systemone`), Ollama (`/v1/systemone`), and vLLM (`/v1/systemone`).
   - **`cloudflare_workers`**: Cloudflare Workers AI (`@cf/cloudflare/clef` via `account_id=`), unwrapping Cloudflare's outer `{"success": true, "result": ...}` envelope.
   - **`openai_decisions`**: OpenAI `POST /v1/decisions` (`input` / `input_json`, ordered `questions` list with `predicate`, `choices: [{value, description}]`, `levels: [{label, description}]`, and list-shaped `answers` and `probabilities`).
   - **`llm_fallback`**: `DM.from_llm(llm)` adapts any generative `LLM` or `ReplayLLM` to the `DM.call` contract so workflows stay portable across providers that lack a dedicated decision model.
3. **Normalizes cross-vendor confidence and probabilities**: Different providers compute wire `confidence` with incompatible formulas (`max(p)` on Google, linear concentration `(K * max_p - 1) / (K - 1)` on TypeSafe/Liquid/Perplexity/OpenAI/Microsoft, normalized negentropy `1 - H(p)/ln(K)` on Upstage/Cloudflare), and most omit `confidence` on binary `noul` answers. `DM` preserves the raw value in `provider_confidence` and computes uniform `confidence` (linear concentration in `[0, 1]`) and `margin` (`p_top1 - p_top2`) directly from `probabilities`.
4. **Records and replays via `MEMORY`**: `dm.record(memory)` writes `kind="decide"` exchanges, and `DM.replay(memory)` returns a thread-safe `ReplayDM` that serves recorded responses offline in sub-millisecond time.

All HTTP uses Python's standard library (`urllib.request`); zero external dependencies are required.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `model_id` | Provider and model in `service:model` format (e.g. `openrouter:typesafe/jev-1.14`, `openai:gpt-6-luna`, `liquid:d1.2`, `ollama:d3:4b`). Bare slugs default to `openrouter:`. |
| `key` | API key for bearer authentication (omitted automatically on keyless local `ollama` / `vllm`). |
| `secret` | Optional API secret for symmetry with `LLM` and `EMBED`. |
| `request_timeout` | Socket timeout in seconds (default `60`). |
| `on_usage` | Optional callback `fn(usage_dict)` invoked with normalized token and `cost` usage. |
| `record` | Optional `MEMORY` instance to record `'decide'` exchanges immediately. |
| `dialect` | Optional explicit dialect override (`'systemone'`, `'openai_decisions'`, `'cloudflare_workers'`) for custom gateways when paired with `base_url=`. |

**Supported services:** `openrouter`, `typesafe`, `openai`, `liquid`, `cloudflare`, `perplexity`, `inception`, `upstage`, `ollama`, `vllm` (plus any `LLM` via `DM.from_llm(llm)`).

## Question Types & Normalized Answer Fields

| Question Type | Spec Shorthand | Normalized Answer Dict |
|---------------|----------------|------------------------|
| `choice` | `{"type": "choice", "instructions": "...", "choices": ["a", "b"] \| {"a": "desc"}}` | `{"type": "choice", "value": "a", "probability": 0.96, "probabilities": {...}, "confidence": 0.92, "provider_confidence": ..., "margin": 0.92}` |
| `noul` | `{"type": "noul", "instructions": "...", "criteria"?: {"true": "...", "false": "..."}}` | `{"type": "noul", "value": True, "probability": 0.94, "probabilities": {"true": 0.94, "false": 0.06}, "confidence": 0.88, "margin": 0.88}` |
| `score` | `{"type": "score", "instructions": "...", "levels": ["Low", "Med", "High"]}` | `{"type": "score", "value": 1.82, "probability": 0.84, "probabilities": {"0": ..., "1": ..., "2": ...}, "legend": ..., "confidence": 0.76, "margin": 0.69}` |
| `box` | `{"type": "box", "instructions": "Locate target"}` | `{"type": "box", "value": {"top": ..., "bottom": ..., "left": ..., "right": ...}, "confidence": ...}` |
| `refusal` | Returned when upstream declines a question | `{"type": "refusal", "value": None, "probability": None, "probabilities": None, "confidence": None, "margin": None}` |

## Usage

```python
from thoughtflow import DM, DECIDE, MEMORY

dm = DM("openrouter:typesafe/jev-1.14", key="sk-or-...")

# 1. Direct multi-question call in a single forward pass
res = dm.call(
    state={"tier": "enterprise", "ticket": "We were billed twice on invoice #8841."},
    questions={
        "owner": {
            "type": "choice",
            "instructions": "Which team owns this ticket?",
            "choices": {
                "billing": "Invoices, duplicate charges, and refunds",
                "engineering": "Product crashes, API errors, and bugs",
            },
        },
        "is_refund": {
            "type": "noul",
            "instructions": "Is the customer requesting money back?",
        },
        "urgency": {
            "type": "score",
            "instructions": "Rate urgency.",
            "levels": ["Low", "Medium", "High"],
        },
    },
)

print(res["answers"]["owner"]["value"])         # "billing"
print(res["answers"]["is_refund"]["probability"])  # e.g. 0.99
print(res["answers"]["urgency"]["value"])       # e.g. 1.18

# 2. Plug directly into DECIDE
memory = MEMORY()
memory.add_msg("user", "The app crashes whenever I open Settings.")
router = DECIDE(
    name="route",
    model=dm,
    choices={"billing": "Charges and refunds", "tech": "Crashes and bugs"},
    prompt="Route this message: {last_user_msg}",
)
memory = router(memory)
print(memory.get_var("route_result"))           # "tech"

# 3. Record and replay offline
rec_mem = MEMORY()
dm.record(rec_mem)
live = dm.call("Hello world", {"greeting": {"type": "noul", "instructions": "Contains greeting?"}})

replay_dm = DM.replay(MEMORY.from_json(rec_mem.to_json()))
assert replay_dm.call("Hello world", {"greeting": {"type": "noul", "instructions": "Contains greeting?"}}) == live
```

## Error Handling

HTTP, network, and malformed-payload errors raise `DecisionError` (exported at `thoughtflow.DecisionError`) with `status`, `body`, and `retryable` attributes and record the message on `dm.last_error`. Inside `DECIDE`, retryable errors (`429`, `5xx`, transport timeouts) honor `max_retries` and `retry_delay`, while deterministic `4xx` errors fail immediately on attempt 1.

## Relationship to Other Primitives

- **`DECIDE`**: `DECIDE` accepts either an `LLM` or a `DM` via `llm=` or `model=`, automatically separating `{var}` state fields from instructions and exposing calibrated probabilities and `min_confidence` / `min_margin` gating when backed by a `DM`.
- **`LLM` & `EMBED`**: Siblings in the Intelligence layer sharing `service:model` routing, `split_call_params`, `normalize_usage`, and `MEMORY` exchange recording.
- **`MEMORY`**: Stores `'decide'` exchanges via `add_exchange` / `get_exchanges(kind='decide')` so entire hybrid `DM` + `LLM` workflows replay deterministically from a single JSON session file.

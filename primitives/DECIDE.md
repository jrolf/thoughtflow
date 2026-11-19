# DECIDE

> A specialized THOUGHT subclass for constrained decision-making across generative LLMs (`LLM`) and structured System-One decision models (`DM`).

## Philosophy

DECIDE exists because many workflows need a bounded, typed judgment rather than free-form prose: routing a support ticket, gating a high-risk tool call, checking whether a condition holds, or scoring an item against a rubric.

By subclassing THOUGHT, DECIDE keeps one uniform `memory = decide(memory)` contract across both model families:

- **With an `LLM` (System Two)**: DECIDE formats the allowed options into the prompt, extracts an unambiguous non-negated choice from the text response, validates it, and runs choice-specific repair retries when needed.
- **With a `DM` (System One)**: DECIDE executes a single forward pass against the decision model's typed endpoint (`choice`, `noul`, `score`, or batched `questions`), automatically isolating untrusted `{variable}` state from instructions and recording calibrated probabilities, normalized `confidence`, and top-2 `margin` in `{name}_outcome`.

Switching a router or guardrail from a generative `LLM` to a `DM` is a one-line model change; downstream code reading `memory.get_var("{name}_result")` stays untouched.

## Decision Modes

| Mode | Configuration | `{name}_result` Value |
|------|---------------|-----------------------|
| **Choice** (default) | `choices=["a", "b"]` or `choices={"a": "desc", "b": "desc"}` | Selected key (`str`), or `default` |
| **Binary (`noul`)** | `choices=bool` (optional `threshold=0.5`) | `True` or `False` (`bool`), with $P(\text{true})$ in `{name}_outcome["probability"]` |
| **Rubric (`score`)** | `levels=["Low: ...", "Medium: ...", "High: ..."]` | Continuous rubric position (`float` in `[0.0, K - 1.0]`) |
| **Multi-question** | `questions={"dept": {...}, "urgent": {...}}` | Dict mapping each question key to its typed answer (`dict`) |

All four modes work on both `DM` and `LLM` instances (multi-question `questions=` on an `LLM` adapts automatically through `DM.from_llm`).

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `name` | Unique identifier driving `{name}_result`, `{name}_outcome`, and `{name}_attempts`. |
| `llm` / `model` | `LLM` or `DM` instance (`model=` is an alias for `llm=`). |
| `prompt` | Prompt or instruction template with `{variable}` placeholders. |
| `choices` | Allowed options (`list` or `dict`), or `bool` for binary `noul` evaluation. |
| `levels` | Ordered rubric level descriptions (lowest to highest) for `score` mode. |
| `questions` | Map of `question_id -> spec` for single-pass multi-question evaluation. |
| `state` | State construction mode on `DM` calls: `"auto"` (default — extracts `{var}` values into a structured `state` dict and rewrites `{var}` to backticked `` `var` `` in `instructions`), `list[str]` of `MEMORY` variable names, `dict` template, or template `str`. |
| `threshold` | Probability threshold for `choices=bool` / `noul` questions (default `0.5`). |
| `min_confidence` | Optional minimum normalized concentration (`0.0..1.0`) required to accept a `DM` answer; below this threshold `DECIDE` substitutes `default` with `outcome["source"] = "low_confidence"`. |
| `min_margin` | Optional minimum top-2 probability gap (`p_top1 - p_top2`) required to accept a `DM` answer. |
| `default` | Fallback value used when retries exhaust, the model refuses, or confidence/margin falls below threshold. |
| `case_sensitive` | Case-sensitive choice matching on the `LLM` path (default `False`). |
| `max_retries` | Maximum attempts (default `5`). On `DM` calls, only transient `429`/`5xx`/timeout errors retry; `4xx` errors and refusals finish in 1 attempt. |
| `retry` | Inherited `THOUGHT` retry policy (`{"on": {"http": "backoff"}, "backoff_base": 0.5, "max_backoff": 8.0, "fallback_llm": ...}`). `fallback_llm` may be a backup `DM` or a generative `LLM` and runs for a single rescue attempt after primary exhaustion or refusal. |
| `visibility` | Inherited `THOUGHT` transcript visibility (`"public"` writes the decision as an assistant message so `CHAT` works seamlessly; `"internal"` / `"silent"` suppresses assistant-message writes). |
| `record_prompt` | When `True`, records the rendered instructions (or question map) to `{name}_prompt` on both `DM` and `LLM` paths. |

## Structured Outcome (`{name}_outcome`)

Every `DECIDE` run writes `{name}_outcome` extending `THOUGHT`'s standard outcome keys (`ok`, `error_class`, `error`, `finish_reason`, `usage`, `attempts`, `validation_messages`) with decision provenance:

- `kind`: `'choice'`, `'noul'`, `'score'`, or `'multi'`
- `value`: Final stored result (after any `default` fallback)
- `raw_value`: Model's un-gated selection before `min_confidence` / `min_margin`
- `source`: `'model'`, `'low_confidence'`, `'default'`, `'refusal'`, or `'error'`
- `probability`: Winning option probability or $P(\text{true})$ (`DM` path)
- `probabilities`: Full discrete probability map (`DM` path)
- `confidence`: Cross-vendor normalized concentration in `[0.0, 1.0]` (`DM` path)
- `provider_confidence`: Raw provider-reported confidence when supplied
- `margin`: Top-2 probability margin `p_top1 - p_top2` (`DM` path)

## Usage

```python
from thoughtflow import DECIDE, DM, LLM, MEMORY

# 1. One-line swap between generative LLM and System-One DM
dm = DM("openrouter:typesafe/jev-1.14", key="sk-or-...")
memory = MEMORY()
memory.add_msg("user", "My blender arrived smashed. I want a refund.")

router = DECIDE(
    name="route",
    model=dm,   # works identically with llm=LLM("openai:gpt-4o", key="...")
    choices={
        "refund": "Damaged goods or money-back requests",
        "tech": "Product bugs, crashes, or login errors",
        "sales": "Pricing, plans, and seat quotes",
    },
    prompt="Route this customer message: {last_user_msg}",
    min_margin=0.50,
    default="escalate",
)
memory = router(memory)
result = memory.get_var("route_result")      # "refund"
outcome = memory.get_var("route_outcome")    # includes probabilities, confidence, margin, source

# 2. Binary gate (`choices=bool`) and rubric score (`levels=[...]`)
is_sec = DECIDE(
    name="touches_auth",
    model=dm,
    choices=bool,
    threshold=0.7,
    prompt="Does {diff} modify authentication or permission checks?",
)

severity = DECIDE(
    name="risk",
    model=dm,
    levels=["Low: docs only", "Medium: isolated handler", "High: auth or schema change"],
    prompt="Rate deployment risk of {diff}.",
)

# 3. Single-pass multi-question triage (`questions={...}`)
intake = DECIDE(
    name="triage",
    model=dm,
    state=["ticket"],
    questions={
        "owner": {"type": "choice", "instructions": "Owner?", "choices": ["billing", "eng"]},
        "is_sev1": {"type": "noul", "instructions": "Production revenue blocked?"},
        "urgency": {"type": "score", "instructions": "Urgency?", "levels": ["P3", "P2", "P1"]},
    },
)
```

## Relationship to Other Primitives

- **`DM`**: Intelligence-layer client for System-One decision models (`openrouter`, `typesafe`, `openai`, `liquid`, `cloudflare`, `perplexity`, `inception`, `upstage`, `ollama`, `vllm`).
- **`THOUGHT`**: Parent class providing context extraction, lazy `_obj_ref` resolution, lifecycle `emit` events, execution history, and pure-JSON `to_dict()` / `from_dict()`.
- **`WORKFLOW`**: Combine fast `DECIDE(model=dm, min_margin=..., default="escalate")` gates with `WORKFLOW.branch(...)` to route clear traffic in a single cheap pass and escalate only genuinely ambiguous cases to an `LLM` or `AGENT`.

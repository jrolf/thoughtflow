# `src/thoughtflow/thoughts/` — Structured Cognitive Subclasses

> **Scope:** Specialized `THOUGHT` subclasses (`DECIDE` and `PLAN`) that turn open-ended model invocations into bounded, validated data structures.
> **Parent class:** [`THOUGHT`](../thought.py) · **Specs:** [`primitives/DECIDE.md`](../../../primitives/DECIDE.md), [`primitives/PLAN.md`](../../../primitives/PLAN.md)

---

## Why Subclass `THOUGHT`?

Base `THOUGHT` owns the universal cognitive step pipeline:
1. Extract context lazily from `MEMORY` (without decompressing unreferenced `>10KB` `_obj_ref` blobs).
2. Render `system_prompt` and `prompt` (`format` or `substitute` mode) and enforce `required_vars`.
3. Call the model, parse, normalize/validate, repair-retry (with optional `double_budget`, `backoff`, and `fallback_llm`), and record `{name}_result` + `{name}_outcome`.

`DECIDE` and `PLAN` inherit that entire lifecycle (hooks, `visibility`, `record_prompt`, JSON `to_dict()` / `from_dict()`, `MEMORY.emit()` telemetry, and `Harness(strict=True)` integration) while specializing **what question is asked** and **what shape is guaranteed back**.

---

## Modules in This Subpackage

| Module | Class | Cognitive Question | Model Support | Stored `{name}_result` Shape |
|--------|-------|--------------------|---------------|------------------------------|
| `decide.py` | `DECIDE` | *"Which option, boolean, rubric score, or triage vector applies?"* | `LLM` (System Two) **or** `DM` (System One) | `str` (`choice`), `bool` (`noul`), `float` (`score`), or `dict` (`questions={...}`) |
| `plan.py` | `PLAN` | *"What sequence of sequential/parallel actions achieves this goal?"* | `LLM` | `list[list[dict]]` — outer steps (sequential), inner tasks (parallel), each with `action`, `params`, and `reason` |

---

## Design Notes & Key Seams

### `DECIDE` (`decide.py`) — Bridging System One (`DM`) and System Two (`LLM`)
- **Dual execution engine:** When given an `LLM`, `DECIDE` formats options into the prompt, parses responses using negation-safe word-boundary matching (`"I do not approve"` never matches `"approve"`), and runs up to 5 repair retries. When given a `DM` (`model=dm` or `llm=dm`), `DECIDE` bypasses text generation completely and executes a single forward pass against the provider's decision endpoint.
- **Automatic prompt-injection isolation (`state="auto"`):** On `DM` calls, `DECIDE` parses `{var}` placeholders in `prompt` via `string.Formatter`, lifts their raw values into a structured `state` dictionary, and rewrites `{var}` to backticked `` `var` `` pointers in `instructions` so untrusted user text never mixes into instructions.
- **Calibrated uncertainty gating:** `min_confidence` (normalized linear concentration) and `min_margin` (`p_top1 - p_top2`) route ambiguous decisions cleanly to `default=` with `outcome["source"] = "low_confidence"` while keeping `outcome["ok"] = True` (distinguishing healthy escalation from transport/refusal failures).

### `PLAN` (`plan.py`) — Inspectable Program Synthesis
- **Data, not hidden execution:** `PLAN` asks the model to propose a bounded data structure (`list[list[dict]]`) and validates every action name, required/optional parameter (`"int?"`), step limit (`max_steps`), parallel limit (`max_parallel`), and single-paragraph `reason`. Your Python code (or the copy-and-edit recipe in [`examples/reference/plan_commit_reflect_loop.py`](../../../examples/reference/plan_commit_reflect_loop.py)) owns execution, approvals, and side effects.
- **Normalization seam (`normalize_plan`):** Subclasses overriding `normalize_plan(parsed_result)` (for example, unwrapping `{"steps": [...]}` envelopes) run through `THOUGHT._prepare_and_validate()` so the exact normalized structure is validated, stored in `{name}_result`, and returned on `plan.last_result`.

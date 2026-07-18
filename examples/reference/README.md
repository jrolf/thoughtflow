# Reference Examples (copy and edit)

These files are **reference recipes**, not a stable ThoughtFlow package surface. Copy `plan_commit_reflect_loop.py` into your project, delete what you do not need, and inject your own governance hooks. **Do not import this directory as a library dependency.**

The flagship example implements the **plan-commit-reflect** loop shape described in [`.PLANS/FOUNDATION_AGENT_LOOP_LEGO_RESPONSE_PLAN.md`](../../.PLANS/FOUNDATION_AGENT_LOOP_LEGO_RESPONSE_PLAN.md): bounded outer/inner loops, plain-data triggers and receipts, native PLAN shape (`list[list[dict]]`), local helpers for receipts, boundary split, and `{step_N_result}` resolution, plus run lifecycle emits on MEMORY.

## Primitive map (where each loop part lives)

| Loop part | ThoughtFlow today | This reference example |
|-----------|-------------------|------------------------|
| State / audit trail | [MEMORY](../../primitives/MEMORY.md) | `agent["memory"]`; run facts via `memory.emit` / `get_emits` |
| Plan generation | [PLAN](../../primitives/PLAN.md) | Demo uses canned plans; swap in `PLAN(...)` in production |
| Cognition gates | [THOUGHT](../../primitives/THOUGHT.md) | Triage/reflection stubs; replace with real THOUGHTs |
| Scheduled entry | [CHRON](../../primitives/CHRON.md) | `make_chron_outer_loop_adapter` closure (docs-only bridge) |
| Side-effect dispatch | [ACTION](../../primitives/ACTION.md) / local handlers | Local `ACTION_CATALOG` dict + handler map (not ActionRegistry) |
| Tool-use loop alternative | [AGENT](../../primitives/AGENT.md) | **Not used** - this loop is planner-writes-a-program |
| Step orchestration alt | [WORKFLOW](../../primitives/WORKFLOW.md) | Optional; this example uses a plain `for` loop |

## What is library contract vs product doctrine

**Library contract (documented elsewhere):** MEMORY event model, PLAN output shape, `{step_N_result}` whole-value refs only (no dotted or bracket paths in v1), CHRON `action(memory)` execution.

**Product doctrine (replace in your copy):** triage verdict strings, boundary action names (`REPLAN`, `DONE`), approval rules, action catalog content, terminal reason vocabulary, effort caps, and fallback messaging policy.

## Safety-critical execution order

For each task, the example first resolves exact whole-value step references, then validates the resolved values with that action's validator, then applies the separate approval policy, and only then calls the handler. An explicitly empty or restricted catalog remains empty or restricted; `None` alone selects the demo defaults. This ordering prevents a placeholder from passing string validation before it resolves to a dict/list receipt, and prevents approval or handlers from seeing unvalidated values.

Receipts use one local convention: `ok` requires a string `summary`, `failed` requires a non-empty string `error` and string `hint`, and `partial` requires a string `summary` and list `gaps`. Factories always return fresh deep-copied dicts. Extension fields pass only through `extra` and cannot replace reserved receipt keys.

`step_results` contains one entry per completed step. A single-task step contributes one receipt; a parallel step contributes an ordered list of receipts. Version 1 resolves only an exact whole-value `{step_N_result}` recursively inside JSON-like params. It rejects missing, future, dotted, bracket, and interpolated references rather than passing unresolved text to a handler.

Run lifecycle events allow only the terminal reasons shown in the example. A run emits exactly one `run_started` and zero-or-one `run_completed` / `run_failed`; trigger persistence is limited to `id`, `source`, and `kind`. Metrics remain an empty JSON-safe dict because this compact recipe does not maintain an accurate task/cycle metric accumulator.

The sub-run recipe deep-copies the parent MEMORY, restricts both catalog and handlers, runs with an explicit cycle bound, and copies only caller-allowlisted JSON-safe outputs. A selected output that cannot be serialized fails the merge without returning partial output state. The recipe reports success, partial completion, or failure from the actual child terminal reason and never merges child state automatically.

## Held items (intentionally not shipped)

These wishes remain **backlog / docs-only** per maintainer review. The reference loop shows hook *slots* where you would call them, but does not implement them:

| Wish | Status | What to do instead |
|------|--------|-------------------|
| `SessionLock` + inbox | HOLD | Single-process queue pattern in your runtime; see plan WP-LEGO-06 |
| `StageContext` budgets | HOLD | Local stage context functions in your agent until two examples share one contract |
| `ActionRegistry` / `ActivityCatalog` | HOLD | Local Python dict as single source of truth (shown in the example) |
| `SubRunScope` class | HOLD | `run_sub_loop` recipe: `parent.copy()`, explicit bounds, manual output merge |
| `Trigger` public normalizer | HOLD | Local `normalize_trigger` with explicit fields; never infer trusted principal |
| `receipt.py` / `plan_utils.py` exports | EXAMPLE FIRST | Helpers live in the example until a second consumer justifies promotion |

## Run locally

No network or API keys required. Requires `memory.emit` / `get_emits` (0.2.5+) or run from a dev checkout:

```bash
PYTHONPATH=src python examples/reference/plan_commit_reflect_loop.py
```

## Run tests

```bash
pytest tests/unit/test_reference_plan_loop.py -v
```

## Related docs

- [PLAN](../../primitives/PLAN.md) - native plan shape and `{step_N_result}` grammar
- [CHRON - Firing into an agent outer loop](../../primitives/CHRON.md#firing-into-an-agent-outer-loop)
- [Example 10: PLAN](../scripts/10_plan.py) - planner walkthrough (bracket-path refs marked unsupported in v1)
- [Serverless handler pattern](../serverless/README.md) - stateless turn architecture

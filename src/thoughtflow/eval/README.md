# `src/thoughtflow/eval/` — Deterministic Evaluation Harness

> **Scope:** Lightweight evaluation suite runner (`Harness`, `TestCase`, `TestResult`, `HarnessResults`) over any `memory -> memory` callable.
> **Related:** [`docs/concepts/replay.md`](../../../docs/concepts/replay.md) · [`examples/scripts/13_record_replay.py`](../../../examples/scripts/13_record_replay.py)

---

## Design Philosophy

Testing AI workflows in ThoughtFlow does not require learning a separate evaluation DSL or spinning up external tracing servers:

1. **A flow is any `memory -> memory` callable** — a single `THOUGHT`, a `DECIDE` router, a governed `AGENT`, a `WORKFLOW`, or a plain Python function.
2. **A `TestCase` is three plain parts** — a `name`, a `setup(memory)` function (or `messages=[...]`), and a `check(memory)` predicate (or `expected=` string/callable).
3. **Isolation & containment** — every case starts from a fresh `MEMORY()`, exceptions are captured into `TestResult.error` while preserving partial `TestResult.memory` for post-mortem inspection, and `Harness` never mutates global state.

---

## Absorbed Errors & `strict=True` Mode

Primitives like `THOUGHT` and `DECIDE` contain failures by design (storing `None` or `default` in `{name}_result` and recording `{name}_outcome["ok"] == False`) so production pipelines can recover gracefully. In an offline test suite, however, an unrecorded `ReplayMissError` or broken schema inside an intermediate step can otherwise be masked by a downstream fallback step.

`Harness` closes that gap automatically:
- Every `TestResult` inspects the resulting `MEMORY` for failed `{name}_outcome` and `{name}_last_error` records and populates `result.absorbed_errors` (and `results.summary()["cases_with_absorbed_errors"]`).
- Passing `harness.run(flow, strict=True)` fails any case that recorded an absorbed error — even when the top-level `check` predicate returned `True` — with a clear `reason` naming the failed step and `error_class`.
- `check` predicates may return either a `bool` or `(passed, reason[, observed])` so failure reports explain *why* an assertion missed without manual `MEMORY` digging.

---

## Quick Example

```python
from thoughtflow import LLM, MEMORY
from thoughtflow.eval import Harness, TestCase

replay_llm = LLM.replay(MEMORY.from_json("tests/fixtures/session.json"))

harness = Harness([
    TestCase(
        name="refund_routing",
        setup=lambda m: m.add_msg("user", "Charged twice on invoice #42"),
        check=lambda m: (
            m.get_var("route_result") == "billing",
            f"expected billing, got {m.get_var('route_result')!r}",
        ),
    ),
])

results = harness.run(build_support_flow(replay_llm), strict=True)
assert results.failed_count == 0, results.summary()
```

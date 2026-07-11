# THOUGHT — Parse, Validate, Retry

THOUGHT is the atomic unit of cognition in ThoughtFlow. One call to a THOUGHT is one complete cognitive step: build a prompt from MEMORY context, call the LLM, parse the response, validate it, retry with repair text when needed, and store the result back on MEMORY.

This page documents the **llm_call** pipeline in detail — especially schema parsing, validation ordering, failure visibility, and the opt-in knobs production harnesses use. For the full primitive reference, see [primitives/THOUGHT.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/THOUGHT.md).

---

## The pipeline (in order)

Understanding order matters. Two validation layers look composable but run **sequentially**:

```
prompt + context
    → LLM call
    → parse_response()        # schema via valid_extract when parsing_rules set
    → validate()              # callable or built-in validator
    → MEMORY update           # {name}_result, logs, optional assistant msg
```

**Schema runs inside `parse_response`.** Your `validation=` callable does not see payloads that fail schema unless you opt into `validation_mode='rescue'`. Unit-testing the callable in isolation is not enough — always exercise the full `THOUGHT(...)` path with canned LLM responses. See `examples/scripts/15_thought_integration_test.py`.

On failure after all retries, THOUGHT stores `None` in `{name}_result` and returns MEMORY normally (no exception). Inspect `{name}_last_error` and structured log events to distinguish misconfiguration from model failure.

---

## Schema language (`parsing_rules`)

Schema-based parsing uses `valid_extract` under the hood:

```python
parsing_rules = {
    "kind": "python",   # or "json"
    "format": { ... },  # the shape you expect
}
```

### Exemplar values are type markers, not defaults

`{"verdict": "continue", "count": 0}` does **not** mean "default to continue" or "default to zero". It means: when present, `verdict` must be a string and `count` must be an int. Prefer type objects in new code: `{"name": str, "count?": int}`.

### The `None` exemplar trap

`{"wish": None}` means **the value must be null** (Python `None`), not "wish may be absent." For optional fields use:

- `"wish?"` in the format dict (key may be omitted)
- omit the key entirely and validate downstream with `validation=`
- `validation_mode='rescue'` when you need a callable to accept shapes the schema cannot express

Enable `strict_schema=True` at construction to catch bare `None` exemplars in CI.

### Optional keys (`?` suffix)

```python
"format": {
    "verdict": "",
    "matched_span?": "",   # may be absent on valid answers
}
```

Keys without `?` are required. Parse-failure messages cite the `?` convention when a required key is missing.

### Branch shapes (`oneOf` dialect)

When the model picks one of several answer shapes (found vs absent, continue vs escalate), use the optional `oneOf` dialect instead of marking every field optional:

```python
"format": {
    "oneOf": [
        {"verdict": "found", "matched_span": ""},
        {"verdict": "absent", "note": ""},
    ]
}
```

Flat `format` dicts remain first-class. `oneOf` is opt-in vocabulary for classification-style thoughts.

---

## Validation

### Built-in strings

`validation='any'`, `'has_keys:k1,k2'`, `'list_min_len:N'`, `'summary_v1'`. The config alias `validator=` behaves identically.

### Callable validators

Canonical return shape is `(bool, why)`. Bare `bool` returns are coerced automatically — `lambda r: True` no longer crashes unpack.

### Rescue mode (opt-in)

```python
THOUGHT(
    name="locator",
    llm=llm,
    prompt="...",
    parsing_rules={"kind": "python", "format": {...}},
    validation=my_validator,
    validation_mode="rescue",  # callable may accept schema misses
)
```

In `rescue` mode, when schema parsing fails but the payload parses structurally, `validate()` is invoked with the parsed object and may return `(True, "rescued: ...")`. Default is `strict`.

---

## Failure visibility

Every failed parse or validation attempt writes a structured JSON event to MEMORY logs:

```json
{"event": "thought_failure", "thought_name": "locator", "attempt": 1, "failure_kind": "schema", "reason": "..."}
```

`failure_kind` is one of: `schema`, `validation`, `extract`, `contract`, `exception`.

MEMORY also receives:

- `{name}_last_error` — dict with `reason`, `failure_kind`, and full `attempts` list
- `{name}_attempts` — integer count for the current run

Optional production hook:

```python
def on_failure(thought, attempt, failure_kind, reason, raw_response=None):
    metrics.increment(failure_kind, thought=thought.name)

THOUGHT(..., on_failure=on_failure)
```

Execution events on completion include `failed: true` when the thought exhausted retries. Legitimate `None` results (e.g. memory_query miss) are not marked failed.

---

## Retry behavior

When validation or parsing fails, THOUGHT appends a **repair suffix** to the prompt and retries up to `max_retries`. Repair text is model-friendly (no raw `NoneType` or JSONPath noise) and includes a compact schema summary when `parsing_rules` are set.

For dict-shaped prompts, `repair_target='section_key'` controls which section receives repair text (default: last key).

### `hold_msg` — clean MEMORY on retries

By default (`hold_msg=False`), failed attempts still write assistant messages to MEMORY — backward-compatible with earlier ThoughtFlow behavior. Set `hold_msg=True` to hold the assistant turn until parse+validate succeed, so retry pollution does not reach downstream context staging.

---

## Production-lane checklist

Opt-in settings for high-volume harnesses (none required for simple use):

| Flag | Purpose |
|------|---------|
| `strict_schema=True` | Construction-time guard against `None` exemplar traps |
| `validation_mode='rescue'` | Let callable validators accept schema-rigid misses |
| `on_failure=fn` | Per-attempt callback for metrics or tracing |
| `hold_msg=True` | Skip assistant messages from failed attempts |
| `oneOf` in format | Branch-shaped classification without weak optional schemas |

---

## Testing pattern

```python
# Canned response through the FULL path — not valid_extract alone
thought = THOUGHT(
    name="locator",
    llm=MockLLM(["{'verdict': 'absent', 'note': 'gone'}"]),
    prompt="Find the clause.",
    parsing_rules={"kind": "python", "format": {"oneOf": [...]}},
    max_retries=1,
)
memory = thought(memory)
assert memory.get_var("locator_result")["verdict"] == "absent"
```

See also [Memory](memory.md) for how failure vars land on MEMORY, and [Deterministic Replay](replay.md) for testing LLM boundaries with recorded exchanges.

# Memory

MEMORY is the event-sourced state container at the center of ThoughtFlow. Messages, variables, logs, reflections, and recorded model exchanges are all events in one ordered, replayable log. Every primitive reads from it and writes to it — the universal contract is `memory = primitive(memory)`.

---

## Events, Not Mutations

Nothing in MEMORY is overwritten. Adding a message appends an event. Setting a variable appends an event. Setting it again appends another. The current state is a view over the log, which means the full history is always available:

```python
from thoughtflow import MEMORY

memory = MEMORY()

memory.add_msg("user", "Hello!")
memory.add_msg("assistant", "Hi there!")

memory.set_var("request_count", 1)
memory.set_var("request_count", 2)

memory.get_var("request_count")          # 2
memory.get_var_history("request_count")  # every change, with sortable stamps
```

This is what makes ThoughtFlow systems debuggable and replayable: the memory *is* the trace.

---

## Messages

`add_msg(role, content="", mode='text', channel='unknown', metadata=None, tool_calls=None, tool_call_id=None, name=None)` appends a message event. Roles include `user`, `assistant`, `system`, and `tool` (for native OpenAI/OpenRouter/Groq tool loops), plus ThoughtFlow-internal roles like `action`, `result`, `query`, `reflection`, and `logger`.

Assistant messages may attach structured `tool_calls`, and `tool` messages attach `tool_call_id` (plus optional `name`). Calling `memory.get_llm_msgs(format="openai")` projects a provider-valid OpenAI history while automatically filtering out internal non-OpenAI roles.

`get_msgs()` retrieves with flexible filtering:

```python
memory.get_msgs()                                  # all messages
memory.get_msgs(include=["user", "assistant"])     # by role
memory.get_msgs(exclude=["action", "result"])      # everything but tool traffic
memory.get_msgs(channel="api")                     # by channel
memory.get_msgs(repr="str")                        # as a printable string
```

Shortcuts for the common cases: `last_user_msg()`, `last_asst_msg()`, `last_result_msg()` — each with `content_only=True` to get just the text.

### Tagging with Metadata

`metadata` attaches provenance to a message, and `get_msgs` can filter on it:

```python
memory.add_msg(
    "system",
    "Relevant context: ...",
    metadata={"internal": True, "source": "rag"},
)

# UI-visible history: drop internal events
memory.get_msgs(exclude_metadata={"internal": True})

# Audit view: only what the system injected
memory.get_msgs(metadata_filter={"source": "rag"})
```

This pattern is the backbone of [RAG, the ThoughtFlow Way](rag.md): system-injected context is tagged, never spliced into the user's words in storage. For optional prompt-injection-style LLM views, see `add_augment()` and `get_llm_msgs(merge_augments=True)` in [RAG](rag.md).

---

## Variables and Objects

Variables carry results between primitives — each THOUGHT stores its output in `{name}_result`, and the next THOUGHT can reference it in its prompt:

```python
memory.set_var("analyze_result", themes, desc="Key themes from the document")
memory.get_var("analyze_result")
```

For large payloads, `set_obj()` stores data in compressed form so the event log stays lean:

```python
memory.set_obj(big_dataframe_dict, name="raw_data", desc="Scraped dataset")
```

---

## Recorded Exchanges

MEMORY also stores model exchanges — the request/response pairs captured by `llm.record(memory)`, `embed.record(memory)`, `dm.record(memory)`, and `tool.record(memory)`:

```python
memory.add_exchange(kind, key, service, model, request, response)  # called by LLM/EMBED/DM/TOOL
memory.get_exchanges(kind="chat")                                  # 'chat' | 'embed' | 'decide' | 'tool'
```

You rarely call these directly; they power the record/replay system. Because exchanges are ordinary events, recordings survive serialization round trips and travel with the rest of the state. See [Deterministic Replay](replay.md).

---

## Typed lifecycle events (`emit`)

For machine-readable facts at loop boundaries (run lifecycle, plan rejection, eval checkpoints), use `emit` instead of prose logs:

```python
memory.emit("plan_rejected", {"reason": "invalid step", "step": 2})
memory.get_emits("plan_rejected")   # filter by kind
memory.get_emits(limit=5)           # most recent five emits
```

Each emit is a normal event with `type='emit'`, a non-empty `kind` string, a JSON-serializable `payload` dict, and `schema_version` (default 1). Payloads are deep-copied on write, and `get_emits` returns independent event copies so read-side mutation cannot alter stored history.

### Channel selection

| Need | Use | Why |
|------|-----|-----|
| Human debugging prose | `add_log(message)` | Legacy string logs for operators |
| Structured lifecycle / eval facts | `emit(kind, payload)` | Harness-friendly typed events |
| Model request/response capture | `add_exchange(...)` | Record/replay only; do not reuse for lifecycle |

Callers must keep emit payloads JSON-safe, redact secrets, and bound size. MEMORY does not enforce payload size limits and is not thread-safe; callers own synchronization.

---

## Context Budgets, Compaction, Scopes, and Suspend/Resume

- **Token-budgeted LLM views (`get_llm_msgs(budget_tokens=...)`):** Drops the oldest unpinned turns for the LLM payload only (pinning `system` messages and the latest `user` message by default, and keeping `assistant(tool_calls)` / `tool` pairs intact). Pass `summarizer=fn(dropped)` to inject a digest system message.
- **Non-destructive compaction (`memory.compact(keep=6)`):** Appends a `system` summary event tagged `metadata={'summary': True, 'internal': True, 'summary_of': [...]}` and emits `memory_compacted`; original events remain in the log while `get_llm_msgs` substitutes the summary.
- **Zero-copy multi-party scopes (`memory.scope(actor, ...)`):** Isolates `read_rooms` / `write_room` message visibility and `{actor}__{key}` variable namespaces (with nested `scope.scope(...)` unwrapping to the root `MEMORY`) so parallel branches or multi-agent debates share one event log without copying events or colliding on `{name}_result`.
- **Idempotent suspend & resume (`suspend` / `resolve_suspension`):** Stores a JSON-safe `_suspension` marker and emits `run_suspended` / `run_resumed`; resolving a second time returns `'already_resolved'` without overwriting the decision.

---

## THOUGHT Outcomes & Failure Variables

Every `THOUGHT` (as well as `DECIDE` and `PLAN`) writes a uniform JSON-safe `{name}_outcome` dict on both success and failure (`ok`, `error_class`, `error`, `finish_reason`, `usage`, `attempts`, `validation_messages`), alongside `{name}_attempts` (total attempts executed) and `{name}_last_error` on failures:

```python
memory = thought(memory)

outcome = memory.get_var("locator_outcome")
# {"ok": False, "error_class": "schema", "error": "...", "finish_reason": "stop",
#  "usage": {...}, "attempts": 2, "validation_messages": [...]}
```

`hold_msg` defaults to `True` on `THOUGHT` so failed drafts are withheld from conversation history unless `hold_msg=False` is explicitly requested. See [Thought](thought.md) for the full parse-validate pipeline.

---

## Serialization

State moves as easily as data:

```python
memory.to_json("state.json")             # JSON export
restored = MEMORY.from_json("state.json")

memory.save("state.pkl")                 # pickle, optionally compressed
restored = MEMORY()
restored.load("state.pkl")

snap = memory.snapshot()                 # dict export
restored = MEMORY.from_events(event_list)  # rehydrate from raw events
```

This is what makes serverless deployment trivial: serialize at the end of one invocation, rehydrate at the start of the next.

---

## Rendering

`render()` produces human- or LLM-readable views of the log:

```python
print(memory.render(format="conversation"))   # clean user/assistant transcript
print(memory.render(format="markdown", include=("msgs", "logs")))
```

---

## Design Philosophy

- **Append-only**: history is never lost, current state is a view
- **One container**: messages, variables, logs, and recordings share one ordered log
- **The memory is the trace**: no separate session or tracing machinery
- **Serializable everywhere**: JSON in, JSON out, replayable on any machine

For the complete API reference, see [primitives/MEMORY.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/MEMORY.md).

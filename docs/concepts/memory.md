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

`add_msg(role, content, mode='text', channel='unknown', metadata=None)` appends a message event. Roles are open-ended — `user`, `assistant`, `system`, plus ThoughtFlow-internal roles like `action` and `result` (tool interactions from the agent loop).

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

MEMORY also stores model exchanges — the request/response pairs captured by `llm.record(memory)` and `embed.record(memory)`:

```python
memory.add_exchange(kind, key, service, model, request, response)  # called by LLM/EMBED
memory.get_exchanges(kind="chat")                                  # read them back
```

You rarely call these directly; they power the record/replay system. Because exchanges are ordinary events, recordings survive serialization round trips and travel with the rest of the state. See [Deterministic Replay](replay.md).

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

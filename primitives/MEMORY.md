# MEMORY

> The event-sourced state container — the brain of the framework.

## Philosophy

All state in ThoughtFlow lives in MEMORY. Messages, variables, logs, reflections — every change is stored as an event with a sortable stamp. This design solves several problems at once: you get a full audit trail of what happened, you can reconstruct state from events for cloud sync or replay, and you have a single place to look when debugging agent behavior. MEMORY is the brain of the framework; primitives that need to read or write state do so through MEMORY.

The event-sourced architecture means you never overwrite history. When a variable is set, the new value is appended to its history. When a message is added, it joins the event stream. Deletions are tombstones, not removals — you can still see that a variable existed and when it was deleted. This makes MEMORY suitable for compliance, debugging, and multi-agent coordination where you need to reason about what happened and when.

## How It Works

MEMORY has four architectural layers. The DATA layer is a dictionary of events keyed by stamp — the single source of truth. The INDEX layer maintains sorted lists of `[timestamp, stamp]` pairs per event type (messages, reflections, logs, variable changes) and a master index for all events. The VARIABLE layer stores variable histories as lists of `[stamp, value]` pairs; each set appends to the list, and deletions append a special tombstone. The OBJECT layer holds compressed large data; values exceeding a size threshold are automatically stored as compressed objects with references in the variable history.

Messages have roles (system, user, assistant, tool, reflection, action, query, result, logger), modes (text, audio, voice), and channels (webapp, ios, android, telegram, whatsapp, slack, api, cli, unknown). Assistant messages may carry structured `tool_calls`, and `tool` messages carry `tool_call_id` (plus optional `name`), which `get_llm_msgs(format='openai')` projects directly into provider-valid OpenAI/OpenRouter/Groq tool turns for `LLM.chat()`. Messages also accept an optional `metadata` dict (e.g. `{'internal': True}`), and `get_msgs` can filter on it via `metadata_filter=` / `exclude_metadata=` — the mechanism behind UI-visible histories and tagged RAG context. `add_augment()` tags context for optional LLM-view merging (`get_llm_msgs(merge_augments=True)` or `AGENT(merge_augments=True)`) without mutating stored user messages. Variables support full history, optional descriptions, and deletion tracking. `prepare_context` builds LLM-ready message lists with smart truncation of older content. Save and load use pickle or JSON; `from_events` rehydrates a MEMORY from an event list for cloud sync.

MEMORY is also the storage substrate for record/replay: `add_exchange()` stores an LLM or EMBED exchange (request + response, keyed by content hash) as an event of type `llm`, and `get_exchanges()` returns them in chronological order. Because exchanges are ordinary events, recordings serialize with `to_json` and survive round-trips like everything else.

The contract is: memory flows through primitives — `memory = primitive(memory)`.

## Inputs & Configuration

| Concept | Description |
|---------|-------------|
| Messages | role, content, mode (text/audio/voice), channel (cli/webapp/api/sms/voice/internal/system) |
| Variables | key, value, optional description; full history retained |
| Logs | Internal log entries (role: logger) |
| Reflections | Agent reasoning traces (role: reflection) |
| object_threshold | Size in bytes above which values auto-compress to object refs (default 10KB) |

**Key methods:** `add_msg`, `add_augment`, `add_log`, `add_ref`, `emit`, `get_emits`, `add_exchange`, `set_var`, `upsert`, `del_var`, `get_var`, `get_var_meta`, `get_var_meta_history`, `find_vars`, `get_events`, `get_msgs`, `get_llm_msgs`, `compact`, `suspend`, `resolve_suspension`, `is_suspended`, `get_suspension`, `get_exchanges`, `last_user_msg`, `last_asst_msg`, `last_result_msg`, `prepare_context`, `scope`, `merge`, `save`, `load`, `to_json`, `from_json`, `copy`, `from_events` (plus monotonic `memory.revision`).

## Scoped Perspectives (`memory.scope`)

Multi-party debates, sealed-bid negotiations, and parallel branches often share one event-sourced `MEMORY` while requiring epistemic isolation between actors. `memory.scope(actor, read_rooms=None, write_room=None, public_keys=(), export_keys=())` returns a zero-copy view over `memory`:

- **Room visibility:** `events`, `get_events`, `get_msgs`, `get_llm_msgs`, `last_user_msg`, `last_asst_msg`, `last_sys_msg`, and `last_result_msg` expose only events matching `read_rooms` (`metadata['room']` or `channel`), while `add_msg` writes into `write_room` (atomically registering custom domain room names in `valid_channels`).
- **Scratchpad & nested scope isolation:** Variable writes default to `{actor}__{key}` unless listed in `export_keys`, while reads check `{actor}__{key}` first and fall back to `public_keys`. Calling `scope.scope(sub_actor, ...)` unwraps directly to the root `MEMORY` under `{actor}__{sub_actor}__{key}`, exporting back to the parent scope (or to root when exported by both). Stock `THOUGHT`, `DECIDE`, `PLAN`, and `CHAT` run directly against a scope without colliding on `{name}_result` or decompressing out-of-scope large objects.

## Channel selection: logs, emits, and exchanges

MEMORY offers three distinct write paths for non-message facts. Pick the channel that matches the consumer:

| Channel | Method | Consumer | Shape |
|---------|--------|----------|-------|
| Human / legacy logs | `add_log(message)` | Operators, debugging prose | Plain string content |
| Machine-readable lifecycle / eval | `emit(kind, payload, schema_version=1)` | Harnesses, batch eval, run lifecycle helpers | Typed dict with `type='emit'`, `kind`, JSON-safe `payload`, `schema_version` |
| Model & tool record / replay | `add_exchange(...)` | `LLM.record` / `LLM.replay`, `EMBED.record`, `TOOL.record` / `ReplayTOOL` | `type='llm'` exchange events (`kind='chat'`, `'embed'`, `'tool'`) |

`emit` stores normal events through the existing `_store_event` path. Payloads are deep-copied on write, and `get_emits` returns independent event copies so callers cannot rewrite stored history through a read result. Callers must keep payloads JSON-serializable, redact secrets, and bound size. MEMORY is not thread-safe; callers own synchronization.

## Usage

```python
from thoughtflow import MEMORY

memory = MEMORY()
memory.add_msg('user', 'Hello!', channel='webapp')
memory.add_msg('assistant', 'Hi there!', channel='webapp')
memory.set_var('session_id', 'abc123', desc='Current session')

context = memory.prepare_context(format='openai')
memory.save('memory.pkl')
```

```python
# Rehydrate from events
memory2 = MEMORY.from_events(event_list, objects=obj_dict)

# Typed lifecycle events for harnesses and eval
memory.emit('plan_rejected', {'reason': 'invalid step', 'step': 2})
events = memory.get_emits('plan_rejected')

# Export to JSON
memory.to_json('backup.json')
memory3 = MEMORY.from_json('backup.json')
```

**Context budgets and compaction:** `get_llm_msgs(budget_tokens=N)` drops the oldest unpinned messages (system messages and the latest user message are pinned by default) using a cheap `len // 4` estimate, or your `token_counter=`. A `summarizer=fn(dropped)` inserts a digest as one system message. Tool results are never returned without their assistant `tool_calls`. `compact(keep=6, summarizer=None)` adds a summary system message tagged `metadata={'summary': True, 'internal': True, 'summary_of': [...]}` and emits `memory_compacted`; originals stay in the log and the LLM view shows the summary instead.

**Suspend and resume:** `suspend(reason, pending=...)` stores a `_suspension` variable (it round-trips through JSON) and emits `run_suspended`. `resolve_suspension(decision)` is idempotent: the first call returns `status='resolved'` and emits `run_resumed`; repeats return `already_resolved` without overwriting the decision. `is_suspended()` and `get_suspension()` read the state.

**Belief tracking, incremental queries, and serverless state:** `upsert(key, value, desc='', metadata=None, source=None)` skips writing a duplicate event when the value and metadata are unchanged, while `get_var_meta(key)` and `get_var_meta_history(key)` read structured provenance. `find_vars(prefix=None, predicate=None, changed_since=None)` and `get_events(..., since=stamp)` support incremental polling without scanning full history. For serverless round-trips, `to_json(..., slim=True, keep_recent_turns=N)` strips logs/reflections and compacts variable history, `memory.revision` provides a monotonic compare-and-swap counter, `memory.merge(other)` performs a stamp-deduped union of concurrent branches, and `save()` / `to_json(filename=...)` write atomically via temp-file + `os.replace`.

## Relationship to Other Primitives

MEMORY is the state container for THOUGHT, AGENT, CHAT, and WORKFLOW. THOUGHT reads context from MEMORY and writes results back. AGENT uses MEMORY for conversation history and tool-call state. DELEGATE passes MEMORY (or a filtered subset) between agents. LLM does not depend on MEMORY; it is a pure interface to model APIs.

## Considerations for Future Development

- Index compaction or pruning for very long sessions
- Optional persistence backends (Redis, SQLite) for production scale
- Channel filtering and role-based context windows for prepare_context
- Compression strategies for object storage (beyond current zlib/base64)

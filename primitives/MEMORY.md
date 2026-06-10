# MEMORY

> The event-sourced state container — the brain of the framework.

## Philosophy

All state in ThoughtFlow lives in MEMORY. Messages, variables, logs, reflections — every change is stored as an event with a sortable stamp. This design solves several problems at once: you get a full audit trail of what happened, you can reconstruct state from events for cloud sync or replay, and you have a single place to look when debugging agent behavior. MEMORY is the brain of the framework; primitives that need to read or write state do so through MEMORY.

The event-sourced architecture means you never overwrite history. When a variable is set, the new value is appended to its history. When a message is added, it joins the event stream. Deletions are tombstones, not removals — you can still see that a variable existed and when it was deleted. This makes MEMORY suitable for compliance, debugging, and multi-agent coordination where you need to reason about what happened and when.

## How It Works

MEMORY has four architectural layers. The DATA layer is a dictionary of events keyed by stamp — the single source of truth. The INDEX layer maintains sorted lists of `[timestamp, stamp]` pairs per event type (messages, reflections, logs, variable changes) and a master index for all events. The VARIABLE layer stores variable histories as lists of `[stamp, value]` pairs; each set appends to the list, and deletions append a special tombstone. The OBJECT layer holds compressed large data; values exceeding a size threshold are automatically stored as compressed objects with references in the variable history.

Messages have roles (system, user, assistant, reflection, action, query, result, logger), modes (text, audio, voice), and channels (cli, webapp, api, sms, voice, internal, system). Messages also accept an optional `metadata` dict (e.g. `{'internal': True}`), and `get_msgs` can filter on it via `metadata_filter=` / `exclude_metadata=` — the mechanism behind UI-visible histories and tagged RAG context. `add_augment()` tags context for optional LLM-view merging (`get_llm_msgs(merge_augments=True)` or `AGENT(merge_augments=True)`) without mutating stored user messages. Variables support full history, optional descriptions, and deletion tracking. `prepare_context` builds LLM-ready message lists with smart truncation of older content. Save and load use pickle or JSON; `from_events` rehydrates a MEMORY from an event list for cloud sync.

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

**Key methods:** `add_msg`, `add_augment`, `add_log`, `add_ref`, `add_exchange`, `set_var`, `del_var`, `get_var`, `get_msgs`, `get_llm_msgs`, `get_exchanges`, `last_user_msg`, `last_asst_msg`, `last_result_msg`, `prepare_context`, `save`, `load`, `to_json`, `from_json`, `copy`, `from_events`.

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

# Export to JSON
memory.to_json('backup.json')
memory3 = MEMORY.from_json('backup.json')
```

## Relationship to Other Primitives

MEMORY is the state container for THOUGHT, AGENT, CHAT, and WORKFLOW. THOUGHT reads context from MEMORY and writes results back. AGENT uses MEMORY for conversation history and tool-call state. DELEGATE passes MEMORY (or a filtered subset) between agents. LLM does not depend on MEMORY; it is a pure interface to model APIs.

## Considerations for Future Development

- Index compaction or pruning for very long sessions
- Optional persistence backends (Redis, SQLite) for production scale
- Channel filtering and role-based context windows for prepare_context
- Compression strategies for object storage (beyond current zlib/base64)

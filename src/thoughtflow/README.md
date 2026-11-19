# `src/thoughtflow/` — Package Architecture & Internals

> **Scope:** Internal module map, layer boundaries, data contracts, and core invariants for the `thoughtflow` Python package.
> **Read alongside:** [`ZEN.md`](../../ZEN.md) · [`primitives/README.md`](../../primitives/README.md) · [`developer/README.md`](../../developer/README.md)

---

## 1. Governing Architectural Invariants

Every module in `src/thoughtflow/` obeys five hard invariants. Any change that violates one of these breaks the architectural guarantees of the library:

1. **Zero external runtime dependencies.** Only Python's standard library (`urllib`, `http.client`, `json`, `ast`, `re`, `zlib`, `subprocess`, `threading`, `datetime`, `zoneinfo`, etc.) may be imported inside `src/thoughtflow/`.
2. **The universal state contract (`memory = primitive(memory)`).** Stateful primitives (`THOUGHT`, `DECIDE`, `PLAN`, `ACTION`, `AGENT`, `WORKFLOW`, `CHAT`) accept a `MEMORY` (or `memory.scope(...)` view) and return it updated. Only Intelligence-layer clients (`LLM`, `EMBED`, `DM`) and declarative capability wrappers (`TOOL`, `MCP`) sit beside `MEMORY` as stateless callables.
3. **Plain-data boundaries.** Results, plans, outcomes (`{name}_outcome`), lifecycle emits (`memory.emit`), suspensions (`_suspension`), and chat completions (`LLM.chat()`) are plain JSON-serializable `dict` / `list` / scalar values — never opaque custom result classes or Pydantic models.
4. **Silent stdout.** Library code in `LLM`, `DM`, `EMBED`, `THOUGHT`, `AGENT`, `TOOL`, and `MCP` must never write diagnostic output to `stdout` (unless explicitly invoking user-facing I/O such as `SAY`, `ASK`, `CHAT`, or `from thoughtflow import this`), because hosts frequently run agents over `stdio` JSON-RPC / MCP channels.
5. **Transport-vs-wire separation (`split_call_params`).** Routing metadata (`base_url`, `extra_headers`, `referer`, `title`, `ollama_url`, `account_id`) is stripped out of wire JSON payloads and excluded from `exchange_key` hashes so recordings replay identically across cloud gateways and local endpoints.

---

## 2. Layered Module Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ORCHESTRATION   workflow.py (WORKFLOW) · chron.py + _cron_expr.py (CHRON)    │
│ COORDINATION    delegate.py (DELEGATE) · chat.py (CHAT)                      │
│ AUTONOMY        agent.py (AGENT, tool_loop) · agents/ (React, Reflect, Plan) │
│ CAPABILITY      tool.py (TOOL, ReplayTOOL) · mcp.py (MCP)                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ COGNITION       thought.py (THOUGHT) · thoughts/ (DECIDE, PLAN)              │
│ OPERATION       action.py (ACTION) · actions/ (14 elemental verbs)           │
│ STATE           memory.py (MEMORY, _MemoryScope) · message.py (Message)      │
│ INTELLIGENCE    llm.py + llm_chat.py + llm_params.py + llm_cache.py          │
│                 providers/ (GroqLLM, CerebrasLLM, OpenRouterLLM)             │
│                 embed.py (EMBED) · dm.py (DM)                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ CROSS-CUTTING   _util.py (stamps, valid_extract, templates) · eval/ (Harness)│
└──────────────────────────────────────────────────────────────────────────────┘
```

| Module / Subpackage | Exports | Responsibility |
|---------------------|---------|----------------|
| `__init__.py` | All 49 public symbols | Single flat namespace (`from thoughtflow import ...`) |
| `memory.py` | `MEMORY` (`_MemoryScope` via `.scope()`) | Event-sourced state log, causal `_seq` ordering, variable histories & tombstones, `>10KB` zlib object store, RAG augments, typed `emit()` events, token-budgeted `get_llm_msgs`, non-destructive `compact()`, idempotent `suspend()` / `resolve_suspension()`, and zero-copy multi-party scopes |
| `message.py` | `Message`, `MessageList`, `normalize_messages` | Optional structured message dataclass supporting `assistant` `tool_calls` and `tool` `tool_call_id` |
| `llm.py` | `LLM`, `OpenAICompatibleLLM`, `ReplayLLM`, `ReplayMissError` | Multi-provider text generation (`call`), streaming, native `output_schema`, `last_finish_reason`, and `kind='chat'` record/replay |
| `llm_chat.py` | `ChatError` (+ `LLM.chat` internals) | Structured OpenAI-compatible completion (`content`, separate `reasoning`, native `tool_calls`, `finish_reason`, `usage`), typed SSE stream events, and cross-thread `cancel=` socket shutdown via `http.client` |
| `llm_params.py` | Internal helpers | Unified parameter bucket pipeline (`LLM_RESERVED_KEYS`, `merge_call_params`, `split_call_params`, `normalize_usage`) |
| `llm_cache.py` | `cached_system`, `cached_message` | Provider-agnostic prompt-caching message markers and Anthropic `cache_control` wire adapter |
| `providers/` | `GroqLLM`, `CerebrasLLM`, `OpenRouterLLM` | Thin `LLM` subclasses encoding production provider defaults (see [`providers/README.md`](providers/README.md)) |
| `embed.py` | `EMBED`, `ReplayEMBED` | Multi-provider vector embeddings (single & batch) with `kind='embed'` record/replay |
| `dm.py` | `DM`, `ReplayDM`, `DecisionError` | Multi-provider structured System-One decision models (`choice`, `noul`, `score`, `box`), cross-vendor linear concentration & margin normalization, `DM.from_llm()` fallback, and `kind='decide'` record/replay |
| `thought.py` | `THOUGHT` | Atomic cognitive step: template rendering (`format` / `substitute`), lazy `_obj_ref` context extraction, `valid_extract` schema parsing, declarative/callable validation, smart retry (`double_budget`, `backoff`, `fallback_llm`), `visibility`, and uniform `{name}_outcome` telemetry |
| `thoughts/` | `DECIDE`, `PLAN` | Specialized `THOUGHT` subclasses for bounded decisions (`LLM` or `DM`) and multi-step DAG planning (see [`thoughts/README.md`](thoughts/README.md)) |
| `action.py` | `ACTION` | Imperative external side-effect wrapper with timing, error containment, and `{name}_result` storage |
| `actions/` | 14 `ACTION` subclasses | Concrete stdlib verbs: `SAY`, `ASK`, `NOTIFY`, `SEARCH`, `FETCH`, `SCRAPE`, `READ`, `WRITE`, `POST`, `SLEEP`, `WAIT`, `NOOP`, `RUN`, `CALL` (see [`actions/README.md`](actions/README.md)) |
| `tool.py` | `TOOL`, `ReplayTOOL` | JSON-Schema callable wrapper with `needs_context=True`, `TOOL.from_action()`, and hermetic `kind='tool'` record/replay/splice |
| `mcp.py` | `MCP` | Stdlib JSON-RPC 2.0 Model Context Protocol client (`stdio` shell/argv + `http`, `prefix=` namespacing, `isError` surfacing) |
| `agent.py` | `AGENT`, `tool_loop` | Autonomous tool loop: governed write-ahead native `LLM.chat()` protocol (`allow`, `policy`, `budget`, `checkpoint`, `decision=` resume) with automatic text-JSON fallback |
| `agents/` | `ReactAgent`, `ReflectAgent`, `PlanActAgent` | Methodology subclasses extending `AGENT` (see [`agents/README.md`](agents/README.md)) |
| `delegate.py` | `DELEGATE` | Multi-agent routing (`handoff`, `dispatch`, `broadcast`) over isolated `memory.copy()` clones |
| `workflow.py` | `WORKFLOW` | Step pipeline with conditions, `ok=` outcome checks, status branching, bounded `while_`, persisted `{name}_log`, and suspend/resume |
| `chron.py`, `_cron_expr.py` | `CHRON` | Recurring job scheduler supporting 5-field cron, `@daily`-style aliases, intervals, serverless `tick()`, daemon threads, and atomic state persistence |
| `chat.py` | `CHAT` | Interactive terminal/notebook turn loop skipping `internal=True` scratchpad messages |
| `eval/` | `eval.Harness`, `eval.TestCase` | Deterministic evaluation harness with `strict=True` absorbed-error detection (see [`eval/README.md`](eval/README.md)) |
| `_util.py` | `EventStamp`, `event_stamp`, `hashify`, `construct_prompt`, `construct_msgs`, `valid_extract`, `ValidExtractError`, `TemplateRenderError` | Base62 sortable stamps, template rendering, schema dialect (`oneOf`, pipe unions, `enum`), balanced JSON/literal extraction, and zlib object compression |
| `this.py` | `zen` | Prints *The Zen of ThoughtFlow* on `from thoughtflow import this` |

---

## 3. Hermetic Record & Replay Across All Four Boundaries

Because `MEMORY` stores every external interaction as a `type='llm'` exchange event keyed by content hash (`exchange_key`), deterministic offline testing works identically across all four external boundaries:

| Boundary | Record | Replay | Exchange `kind` | Notes |
|----------|--------|--------|-----------------|-------|
| **Text / Chat Models** | `llm.record(memory)` | `LLM.replay(memory)` -> `ReplayLLM` | `'chat'` | Covers both `llm.call()` (`list[str]`) and `llm.chat()` (dict + stream events) |
| **Embeddings** | `embed.record(memory)` | `EMBED.replay(memory)` -> `ReplayEMBED` | `'embed'` | Preserves single vs batch return shape |
| **Decision Models** | `dm.record(memory)` | `DM.replay(memory)` -> `ReplayDM` | `'decide'` | Preserves calibrated `probabilities`, `confidence`, and `margin` |
| **Tools & MCP** | `tool.record(memory)` | `tool.replay(memory)` / `TOOL.replay_all(...)` -> `ReplayTOOL` | `'tool'` | Compresses large tool results via `memory.objects`; `on_miss='live'` enables time-travel splice debugging |

# `src/thoughtflow/actions/` — Elemental Action Primitives

> **Scope:** 14 zero-dependency `ACTION` subclasses ("agent verbs") plus internal HTTP and `{variable}` substitution helpers.
> **Parent class:** [`ACTION`](../action.py) · **Specs:** [`primitives/ACTION.md`](../../../primitives/ACTION.md) and per-verb files in [`primitives/`](../../../primitives/README.md)

---

## `ACTION` vs `TOOL`: The Core Boundary

ThoughtFlow separates **imperative execution** from **model-selected capability**:

- **`ACTION` (this directory) is imperative.** Your Python workflow, `CHRON` job, or `WORKFLOW` step invokes it deterministically: `memory = action(memory, **kwargs)`. It logs execution timing, contains exceptions into structured error dicts rather than crashing the flow, and stores results in `{name}_result` (or `store_as=`).
- **`TOOL` (`../tool.py`) is declarative.** It attaches a JSON Schema so an `LLM` / `AGENT` can choose *whether* and *how* to call a function. Any `ACTION` can be promoted into a context-aware `TOOL` via `TOOL.from_action(action, description=..., parameters=...)`, which automatically passes the active `MEMORY` into the action function via `needs_context=True`.

---

## Catalog of the 14 Elemental Verbs

Every verb is implemented purely with the Python standard library (`urllib.request`, `html.parser`, `subprocess`, `os`, `time`):

| Category | Class | Module | Default Result Variable | What It Does |
|----------|-------|--------|-------------------------|--------------|
| **Communication** | `SAY` | `say.py` | `{name}_output` | Emit formatted text to stdout, callback, or `MEMORY` channel |
| **Communication** | `ASK` | `ask.py` | `{name}_response` | Prompt a human user (stdin or custom `input_fn`) with optional validation/retries |
| **Communication** | `NOTIFY` | `notify.py` | `{name}_result` | Send notifications via console, webhook HTTP POST, or custom handler |
| **Retrieval** | `SEARCH` | `search.py` | `{name}_results` | Normalized web search across DuckDuckGo (keyless), Brave, Exa, and Google Custom Search |
| **Retrieval** | `FETCH` | `fetch.py` | `{name}_response` | HTTP requests (`GET`, `POST`, etc.) with headers, query params, JSON auto-parse, and retries |
| **Retrieval** | `SCRAPE` | `scrape.py` | `{name}_content` | Fetch a URL and extract raw HTML, clean Markdown, or structured metadata/headings/links/tables |
| **Retrieval** | `READ` | `read_file.py` | `{name}_content` | Read local files as `text`, `json`, `lines`, or `bytes` with max-size guards |
| **Persistence** | `WRITE` | `write_file.py` | `{name}_result` | Write/append text, JSON, or lines to disk with optional parent-dir creation and `overwrite` guard |
| **Persistence** | `POST` | `post.py` | `{name}_response` | Convenience HTTP POST (`json`, `form`, or `raw`) built over `_http.py` |
| **Temporal** | `SLEEP` | `sleep.py` | `{name}_result` | Pause execution for fixed or `{var}`-resolved seconds (rate limiting / polling) |
| **Temporal** | `WAIT` | `wait.py` | `{name}_result` | Poll `condition(memory)` at `poll_interval` until truthy or `timeout` |
| **Temporal** | `NOOP` | `noop.py` | `{name}_result` | Explicit no-op placeholder step for `WORKFLOW` branches and tests |
| **Execution** | `RUN` | `run.py` | `{name}_result` | Execute subprocess commands (`shell=False` argv list by default) with timeout, `cwd`, and `env` |
| **Execution** | `CALL` | `call.py` | `{name}_result` | Invoke an arbitrary Python function with `{var}`-substituted arguments and optional timeout |

---

## Internal Support Modules

- **`_substitution.py`:** Implements recursive `{variable}` placeholder resolution (`substitute(value, memory)` and `resolve_value(...)`) across strings, dicts, lists, and `callable(memory)` values so action configs can bind dynamically to `MEMORY` state at call time.
- **`_http.py`:** Shared stdlib `urllib.request` client handling timeouts, header normalization, JSON encoding/decoding, and structured HTTP error capture for `FETCH`, `POST`, `SEARCH`, `SCRAPE`, and `NOTIFY`.

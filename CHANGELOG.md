# Changelog

All notable changes to ThoughtFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `LLM.chat()`: structured chat completion for OpenAI-compatible services (`openai` with any `base_url`, `openrouter`, `groq`). Returns the whole assistant message as one dict: `content`, `reasoning` (kept separate from the answer), native `tool_calls` with parsed `arguments`, `finish_reason`, normalized `usage` (including provider-reported `cost`), and `model`. Messages and tools pass through verbatim.
- `LLM.chat(stream=True)`: generator of typed events (`text_delta`, `reasoning_delta`, `tool_call_delta`, `done`) including tool-call deltas.
- `LLM.chat(cancel=threading.Event())`: abort from another thread; the socket is shut down at once, including while waiting for the first byte. A stream ends with a `done` event whose `finish_reason` is `aborted`.
- `ChatError` (exported) with `status`, `body`, and `retryable`. `chat` raises instead of printing, so hosts that use stdout as a protocol channel are safe.
- Record and replay support for `chat`: `LLM.record` captures structured exchanges and `ReplayLLM.chat` serves them, replaying streams as events.
- `MCP(url, headers=None, timeout=60)`: extra HTTP headers (for example `Authorization`) and a per-request timeout for HTTP servers. Stdio servers ignore both.
- `parse_cron` accepts the aliases `@hourly`, `@daily`, `@midnight`, `@weekly`, `@monthly`, `@yearly`, `@annually`.
- `TemplateRenderError` (exported) raised when prompt template rendering fails or configured `required_vars` are missing.
- `THOUGHT` / `DECIDE` / `PLAN` structured `{name}_outcome` variable (`ok`, `error_class`, `error`, `finish_reason`, `usage`, `attempts`, `validation_messages`) and `thought_completed` / `thought_failed` lifecycle emits on `MEMORY`.
- `LLM.last_finish_reason` normalized across providers and `allow_reasoning_fallback=False` default so truncated chain-of-thought replies do not pass as valid completions.
- `Harness.run(..., strict=False)` absorbed-error tracking (`TestResult.absorbed_errors`, `reason`, `observed`, preserved partial `memory`, and `summary()['cases_with_absorbed_errors']`).
- `MEMORY` native tool-turn support: `'tool'` role, structured `tool_calls` on assistant messages, `tool_call_id` and `name` on tool messages, and `MEMORY.get_llm_msgs(format='openai')` for provider-valid `LLM.chat()` message histories (`Message.assistant(tool_calls=...)` and `Message.tool(...)` updated to match).
- `MEMORY.scope(actor, read_rooms=None, write_room=None, public_keys=(), export_keys=())`: zero-copy scoped perspective over a shared `MEMORY` isolating room/channel visibility and `{actor}__{key}` scratchpad variables for multi-party and parallel flows; `get_llm_msgs` also gains `channel`, `metadata_filter`, and `exclude_metadata` passthrough.
- `TOOL.record(memory)`, `tool.replay(memory, on_miss='raise')` (`ReplayTOOL`, exported), and `TOOL.replay_all(...)`: hermetic tool and MCP record/replay/splice (`on_miss='live'`) backed by `MEMORY` exchanges.
- Declarative JSON-serializable rule lists on `THOUGHT(validation=[...])` (`in`, `non_empty`, `range`, `regex`, `has_keys`) that round-trip cleanly through `to_dict()` / `from_dict()`.
- `MCP(..., prefix=None)` / `list_tools(prefix=None)` for multi-server tool namespacing and `list[str]` stdio argv support (`shell=False`).

### Changed
- `THOUGHT` (and `DECIDE`/`PLAN`) fail loudly before calling the LLM when `template_mode='format'` cannot render a prompt or when `required_vars` are missing, recording `failure_kind='template'`.
- `LLM` now defaults `request_timeout` to `120` seconds (pass `request_timeout=None` for blocking), rejects unsupported `n > 1` on providers/streaming that cannot honor it, and stops printing HTTP errors to stdout in `call()`.
- `THOUGHT` now defaults `hold_msg=True` (keeping failed retry drafts out of chat history), defaults `add_reflection=False` (avoiding duplicate answer events), sets `{name}_attempts` to total attempts on both success and failure, and treats `finish_reason='length'`, empty replies, HTTP errors, and `ReplayMissError` as explicit failed attempts.
- `THOUGHT.get_context()` resolves compressed `_obj_ref` variables lazily only when referenced by the prompt or explicit var lists, avoiding eager decompression of unrelated large objects.

### Fixed
- `DELEGATE._copy_memory` now uses `memory.copy()` so delegated agents receive actual variable values, descriptions, and tombstones instead of nested `[stamp, value]` history lists.
- `DECIDE.parse_response` requires an exact, leading, or single non-negated word-boundary choice match so negated replies such as `"I do not approve this. Revise."` trigger repair retries instead of matching `"approve"`.
- `ReactAgent` preserves multi-line `Final Answer:` responses and appends a policy-veto `Observation:` when `on_tool_call` returns `False`.
- `WORKFLOW` treats exceptions raised inside `condition` callables as step errors honoring `on_error` rather than silently skipping as `condition_false`.
- `CHRON` captures returned `MEMORY` objects from job actions, writes `state_file` atomically, and surfaces corrupt/failed state I/O via `RuntimeWarning` + `last_state_error` (or raises with `on_state_error='raise'`).
- `MEMORY.from_events()` now persists and sorts by monotonic per-event `_seq` on sub-millisecond timestamp ties so unordered event rehydration preserves variable write order and deletion tombstones.
- `THOUGHT.to_dict()` strips non-JSON-serializable callables from `config` and `THOUGHT.from_dict()` pops explicit constructor keys from `config` instead of raising `TypeError` on `max_retries`.
- `CHAT._extract_response()` walks new assistant messages in reverse chronological order (skipping `metadata={'internal': True}`) instead of iterating an unordered `set` diff.
- `MCP.call_tool()` raises `RuntimeError` when an MCP server returns `isError=True` instead of returning error text as a normal tool result.
- `humanize_schema_error()` scrubs runtime `at 0x...` heap addresses so `ast.literal_eval` repair suffixes remain deterministic for replay.
## [0.2.5] - 2026-07-17

Foundation Agent loop response: lifecycle emits on MEMORY, THOUGHT prompt/history improvements, PLAN normalization fix, and a copy-and-edit plan-commit-reflect reference recipe.

### Added
- `MEMORY.emit()` and `get_emits()` for JSON-safe, typed lifecycle and evaluation events
- THOUGHT `template_mode='substitute'` for exact `{key}` replacement in JSON-heavy prompts
- THOUGHT `include_history=False` for requests containing only the configured system and user prompts
- Executable plan-commit-reflect reference recipe with receipts, bounded loops, step-result resolution, lifecycle events, sub-run isolation, and CHRON adapter guidance

### Changed
- THOUGHT now builds included history through `MEMORY.get_llm_msgs()` and no longer applies bare substring replacement to historical message content
- THOUGHT prompt context now exposes each MEMORY variable's latest value instead of its internal event history
- Dict-shaped prompt sections retain their previous format-mode behavior and support exact placeholder rendering in substitute mode
- README aligned with current capabilities (lifecycle emits, RAG augments, THOUGHT rendering options)

### Fixed
- PLAN now validates, returns, and stores the same value produced by `normalize_plan()`, including across validation retries

## [0.2.4] - 2026-07-11

### Fixed
- MEMORY index tie-breaking: events with identical `dt_utc` now preserve insertion order (fixes flaky replay and get_events tests on CI)
- `add_exchange()` stamp now includes response payload so duplicate-key recordings are not overwritten

## [0.2.3] - 2026-07-11

### Fixed
- Python 3.9 import failure: `TypeAlias` removed from `message.py` (stdlib support starts at 3.10)

## [0.2.2] - 2026-07-10

Production-hardening release: THOUGHT/PLAN parsing improvements (Foundation Agent feedback) plus unified LLM param pipeline, prompt caching, and native provider convenience classes.

### Added
- THOUGHT `on_failure=` hook and structured failure events on MEMORY (`{name}_last_error`, `{name}_attempts`)
- THOUGHT opt-in production lane: `validation_mode='rescue'`, `strict_schema=True`, `hold_msg=True`, `repair_target=`
- `valid_extract` optional `oneOf` schema dialect for branch-shaped responses
- PLAN `normalize_plan()` subclass hook and aggregate missing-param error messages
- LLM `last_error`, `last_usage`, opt-in `request_timeout=`, `on_usage=` callback
- Unified model-param pipeline (`split_call_params`) — transport keys never leak into JSON bodies
- Prompt caching: `cached_system()`, `cached_message()`, `cache=True` on messages; Anthropic `cache_control` wire adapter
- Native provider classes: `GroqLLM`, `CerebrasLLM`, `OpenRouterLLM`
- `docs/concepts/thought.md` — parse-validate pipeline guide
- Regression tests: `test_foundation_agent_response.py`, `test_llm_provider_integration.py`
- Example: `examples/scripts/15_thought_integration_test.py`
- Integration smoke tests: `tests/integration/test_llm_providers.py`, `test_embed_providers.py`

### Changed
- Validation callables may return bare `bool` (coerced to tuple automatically)
- Parse-failure and repair-suffix messages are model-friendly
- `parser='json'` uses balanced JSON extraction
- Execution events include `failed: true` when retries exhausted with error
- OpenAI-compatible choice extraction falls back to `message.reasoning` when `content` is empty
- Expanded `docs/concepts/llm.md`, `primitives/LLM.md`, `primitives/THOUGHT.md`, `primitives/PLAN.md`

### Fixed
- Bare-bool `validation=` lambdas no longer crash unpack
- PLAN param validation reports all missing params at once
- OpenRouter `referer`/`title` no longer leak into request JSON body
- EMBED Groq calls include User-Agent (Cloudflare HTTP 1010 without it)
- EMBED `text-embedding-004` aliases to `gemini-embedding-001`; `last_error` surfaced on failures

---

## [0.2.0] - 2026-06-10

The release where ThoughtFlow's deterministic-replay story becomes real —
grown from MEMORY itself, with zero new concepts.

### Added
- **Record/replay system.** `llm.record(memory)` captures every LLM exchange
  (request + response, keyed by content hash) as MEMORY events. `LLM.replay(memory)`
  returns a `ReplayLLM` — a drop-in LLM that serves recorded responses
  deterministically: offline, instant, no API keys. Misses fail loudly
  (`ReplayMissError`) or fall back to a live LLM via `on_miss=`.
- `EMBED.record()` / `EMBED.replay()` / `ReplayEMBED` — the identical seam for
  the embedding boundary
- `MEMORY.add_exchange()` / `MEMORY.get_exchanges()` — the event-sourced storage
  powering record/replay; recordings survive `to_json`/`from_json` round-trips
- **Working eval harness.** `thoughtflow.eval.Harness` now actually runs:
  a `TestCase` is a name + setup + check predicate over MEMORY; `Harness.run(flow)`
  executes any `memory -> memory` callable per case in isolated MEMORYs,
  containing exceptions as failures. The whole package is ~230 lines.
- **Streaming through THOUGHT.** New `on_token=` config hook: when set, the LLM
  response streams through the hook chunk-by-chunk, then the complete text flows
  through the normal parse/validate/store pipeline. LLMs without streaming
  support fall back to a normal call automatically.
- `OpenAICompatibleLLM` exported from the package root (local servers: vLLM,
  LM Studio, llama.cpp, MLX)
- Python 3.13 classifier
- Unit tests for record/replay (round-trips, hash stability, miss behavior,
  end-to-end THOUGHT replay), the eval harness, on_token streaming, and
  validation-spelling equivalence
- `MEMORY.add_augment()` — store context tagged for optional LLM-view merging
  (e.g. RAG chunks) without mutating user messages in the event log
- `MEMORY.get_llm_msgs(merge_augments=False)` — build LLM-ready message dicts;
  when `merge_augments=True`, fold `metadata['augments'] == 'last_user'`
  events into the preceding user turn for the model payload only
- `AGENT(merge_augments=False)` — opt-in flag to use the merged LLM view in
  `_build_messages()`; default behavior unchanged
- Addresses [#15](https://github.com/jrolf/thoughtflow/issues/15) — optional
  support for prompt-injection-style RAG while preserving event-sourced storage

### Changed
- `THOUGHT` validation: `validation=` is the canonical spelling and now accepts
  both callables and built-in strings (`'any'`, `'has_keys:...'`,
  `'list_min_len:N'`, `'summary_v1'`); the `validator=` config key remains fully
  supported and behaves identically
- Standardized brand casing to "ThoughtFlow" across source docstrings, ZEN.md,
  and project docs

### Fixed
- `MEMORY.copy()` — no longer stores a module reference on the instance
  (`bisect` is now a module-level import), so deep copy works; the previously
  skipped test is restored and expanded
- Anthropic: system prompts now use the top-level `system` field (not `messages`)
- Gemini: map `max_tokens` / `temperature` / `top_p` to `generationConfig`
- `THOUGHT`: `parse='json'` now aliases `parser='json'`; fenced JSON parsing improved

### Removed
- `thoughtflow.trace` (Session/Event/TraceSchema) — superseded by MEMORY-native
  record/replay. The subsystem duplicated MEMORY's event log in a foreign idiom,
  and its `load()`/`run()` methods were unimplemented stubs with no user surface.
  MEMORY's JSON serialization already carries a schema version field.
- `thoughtflow.eval.Replay` stub — replaced by the working `ReplayLLM`
- Vestigial pyproject extras (`openai`, `anthropic`, `local`, `all-providers`) —
  these installed SDKs the zero-dependency core never imports (leftovers from a
  removed adapter-era design)
- Adapter-era integration test files (`test_openai_adapter.py`,
  `test_anthropic_adapter.py`) and the legacy `MockAdapter` test fixture —
  all referenced a `thoughtflow.adapters` module that no longer exists

---

## [0.1.3] - 2026-06-10

### Added
- `MEMORY.last_result_msg()` — convenience accessor for the most recent `result` role message (mirrors `last_user_msg`, `last_log_msg`, etc.)
- `MEMORY.add_msg(..., metadata=...)` — optional per-message metadata dict for UI and RAG tagging (e.g. `{'internal': True}`)
- `MEMORY.get_msgs(..., metadata_filter=..., exclude_metadata=...)` — filter messages by metadata for UI-visible history
- `AGENT._strip_markdown_fences()` — strips wrapping markdown code fences before JSON tool-call parsing
- Unit tests for all of the above

### Fixed
- Pre-commit `block-ai-trailer` hook now passes the commit message filename (required by `block-ai-contributors.sh`)
- Closes [#14](https://github.com/jrolf/thoughtflow/issues/14) — message metadata for UI filtering

---

## [0.1.2] - 2026-04-01

### Added
- `LLM` constructor now accepts `**kwargs` for default call parameters — `temperature`, `max_tokens`, `top_p`, `frequency_penalty`, and `presence_penalty` (plus any provider-specific key) can be set once at construction and apply to every subsequent `.call()` invocation
- `LLM.default_params` attribute exposes the stored defaults for inspection
- Per-call `params` continue to override defaults on a per-key basis
- 8 new unit tests covering default storage, merge precedence, non-mutation between calls, and all five parameters passing through to the API payload
- Updated `primitives/LLM.md` with full parameter reference table and constructor-defaults usage examples
- Updated `docs/quickstart.md` with "Setting Default Parameters" section

### Fixed
- Closes [#4](https://github.com/jrolf/thoughtflow/issues/4) — feature request: `temperature` argument for LLM creation

---

## [0.1.1] - 2026-04-01

### Added
- `hooks/block-ai-contributors.sh` — portable pre-commit/commit-msg hook that blocks commits attributed to non-human identities (checks author name/email and Co-authored-by trailers against a configurable blocklist)
- `.pre-commit-config.yaml` now includes `block-ai-author` (pre-commit stage) and `block-ai-trailer` (commit-msg stage) hooks

### Fixed
- Removed erroneous `Co-authored-by: Cursor` and `Made-with: Cursor` trailers from five historical commits; git history rewritten to ensure only human contributors are attributed

---

## [0.1.0] - 2026-04-01

### Added
- `PlanActAgent` fenced-JSON fallback parsing -- silently recovers when the LLM wraps its plan output in markdown code fences (contributed by @cmgoffena13 via PR #5)
- `PlanActAgent` execution logging -- plan generation and replanning events are now recorded in `execution_log` and written to conversation memory for full traceability (contributed by @cmgoffena13 via PR #5)
- Pre-commit hooks via `prek` -- `ruff check` on commit, `pytest tests/unit/` on pre-push
- `ruff.toml` -- project-wide linter configuration (Pyflakes F-rules only; no style enforcement)
- `chore/` branch naming convention added to CONTRIBUTING.md

### Changed
- Ruff configured as bug-catcher only (unused imports, undefined names, unused variables). No formatter, no style or modernization rules.
- `CONTRIBUTING.md` updated to reflect actual dev setup -- removed `ruff format`, type hints requirements, and `mypy` from the checklist
- Dev dependency swapped from `pre-commit` to `prek`

### Fixed
- `LLM.__init__` now correctly parses model names containing colons (e.g. `ollama:mistral:7b`) by splitting on the first colon only (contributed by @cmgoffena13 via PR #3)
- `memory.render()` calls in example scripts corrected from stale `output_format=` argument to `format=` (contributed by @orliesaurus via PR #7)
- Dead code removed across `src/` and `tests/` -- unused imports, unused variables, and redefined names cleared

---

## [0.0.9] - 2026-03-18

### Added
- `PROVIDER_ROLE_MAP` — module-level configuration in `llm.py` mapping ThoughtFlow-internal roles (`action`, `result`) to each provider's native role strings
- `LLM._map_roles()` — translates roles using `PROVIDER_ROLE_MAP` after structural normalization
- `LLM._prepare_messages()` — convenience pipeline: `_normalize_messages()` then `_map_roles()`; used by all `_call_*` methods
- `AGENT.LLM_ROLES` — class-level set controlling which MEMORY roles are forwarded to the LLM (default: `user`, `assistant`, `system`, `action`, `result`); subclasses can override
- Ollama `_message_to_choice()` — extracts `tool_calls` from Ollama responses into content text (contributed by @cmgoffena13 via PR #1)

### Changed
- All `_call_*` methods and `_stream()` now use `_prepare_messages()` instead of `_normalize_messages()` directly
- `_call_gemini()` no longer has an inline role translation dict; Gemini roles are handled centrally by `PROVIDER_ROLE_MAP`
- `AGENT._build_messages()` and `ReactAgent._build_messages()` now filter memory messages to `LLM_ROLES`, preventing non-LLM roles from reaching the provider API

### Fixed
- Agents using Ollama/Gemini no longer infinite-loop when tool calls produce `"action"`/`"result"` roles that the provider silently discards
- Ollama responses containing `tool_calls` are now correctly extracted and returned (previously only `content` was read)

---

<!-- Release links -->
[Unreleased]: https://github.com/jrolf/thoughtflow/compare/v0.2.5...HEAD
[0.2.5]: https://github.com/jrolf/thoughtflow/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/jrolf/thoughtflow/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/jrolf/thoughtflow/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/jrolf/thoughtflow/compare/v0.2.0...v0.2.2
[0.2.0]: https://github.com/jrolf/thoughtflow/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/jrolf/thoughtflow/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/jrolf/thoughtflow/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jrolf/thoughtflow/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jrolf/thoughtflow/compare/v0.0.9...v0.1.0
[0.0.9]: https://github.com/jrolf/thoughtflow/compare/v0.0.8...v0.0.9

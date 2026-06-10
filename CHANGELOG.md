# Changelog

All notable changes to ThoughtFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

### Fixed
- Nothing yet

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
[Unreleased]: https://github.com/jrolf/thoughtflow/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jrolf/thoughtflow/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/jrolf/thoughtflow/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/jrolf/thoughtflow/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jrolf/thoughtflow/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jrolf/thoughtflow/compare/v0.0.9...v0.1.0
[0.0.9]: https://github.com/jrolf/thoughtflow/compare/v0.0.8...v0.0.9

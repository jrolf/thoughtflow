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
[Unreleased]: https://github.com/jrolf/thoughtflow/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/jrolf/thoughtflow/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jrolf/thoughtflow/compare/v0.0.9...v0.1.0
[0.0.9]: https://github.com/jrolf/thoughtflow/compare/v0.0.8...v0.0.9

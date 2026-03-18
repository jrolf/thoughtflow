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

## [0.1.0] - Unreleased

### Added
- First alpha release
- Core primitives: Agent, Message, Adapter
- OpenAI adapter implementation
- Basic tracing infrastructure
- Unit test suite
- Documentation site

---

<!-- Release links -->
[Unreleased]: https://github.com/jrolf/thoughtflow/compare/v0.0.9...HEAD
[0.0.9]: https://github.com/jrolf/thoughtflow/compare/v0.0.8...v0.0.9
[0.1.0]: https://github.com/jrolf/thoughtflow/releases/tag/v0.1.0

# `tests/` — Test Suite Architecture & Conventions

> **Scope:** Unit tests (`tests/unit/`) and opt-in live provider smoke suites (`tests/integration/`).
> **Run fast offline suite:** `pytest tests/unit -q`

---

## Philosophy: Fast, Hermetic, Regression-Focused

ThoughtFlow's test suite enforces three guarantees:
1. **Zero network & zero flakiness in `tests/unit/`** — All ~984 unit tests run offline in ~10 seconds using scripted in-memory servers (`ThreadingHTTPServer` on `127.0.0.1`), `urllib` boundary patches, `MockLLM` fixtures (`conftest.py`), and `MEMORY`-backed `ReplayLLM` / `ReplayDM` / `ReplayEMBED` / `ReplayTOOL` recordings.
2. **Zero-dependency proof in CI** — `.github/workflows/test.yml` installs `pip install -e .` + `pytest` alone (with no optional extras) and runs the entire unit suite to prove the core package never acquires hidden third-party imports.
3. **Public contract over private internals** — Tests exercise full primitive lifecycles (`memory = primitive(memory)`, JSON serialization round-trips, thread-pool concurrency, crash/suspend recovery) rather than brittle private implementation details.

---

## Directory Map

### `tests/unit/` — Deterministic Offline Suite (Always Run)

| Test File | Primary Surface Covered |
|-----------|-------------------------|
| `test_llm.py` | `LLM.call`, message normalization, role mapping, streaming, `output_schema`, local `base_url` |
| `test_llm_chat.py` | `LLM.chat` native `tool_calls`, separate `reasoning`, SSE deltas, cross-thread `cancel=` socket abort, `ReplayLLM.chat` |
| `test_llm_provider_integration.py` | `split_call_params`, `GroqLLM`, `CerebrasLLM`, `OpenRouterLLM`, `cached_system`, `last_finish_reason`, `request_timeout` |
| `test_dm.py` | `DM`, `ReplayDM`, `DecisionError`, System-One / OpenAI `/v1/decisions` / Cloudflare / Ollama codecs, concentration/margin math, all 4 `DECIDE` modes, state auto-isolation, uncertainty gating, `fallback_llm` |
| `test_embed.py` | `EMBED` single/batch calls across OpenAI, Gemini, Ollama, custom `base_url`, and `ReplayEMBED` |
| `test_memory.py` | `MEMORY` events, causal `_seq` branch merges, var histories & tombstones, `>10KB` compression, `tool` role + `get_llm_msgs(format='openai')`, `budget_tokens=`, `compact()`, `suspend()`/`resolve_suspension()`, `memory.scope()` nesting & thread safety |
| `test_message.py` | `Message` dataclass, `assistant(tool_calls=...)`, `Message.tool(...)`, `normalize_messages` |
| `test_thought.py` | `THOUGHT`, `DECIDE`, `PLAN`: template errors, schema dialect (`oneOf`, unions, `enum`), declarative rules, `retry` (`double_budget`, `backoff`, `fallback_llm`), `visibility`, `{name}_outcome`, lazy `_obj_ref` context, JSON `to_dict`/`from_dict` |
| `test_foundation_agent_response.py` | Production hardening regressions (`rescue` mode, `strict_schema`, `normalize_plan`, `substitute` templates, `emit`) |
| `test_action.py`, `test_actions.py` | Base `ACTION` contract and all 14 stdlib action subclasses (`SAY`, `SEARCH`, `SCRAPE`, `RUN`, etc.) |
| `test_tool.py` | `TOOL` schema normalization, `needs_context=True`, `TOOL.from_action`, `TOOL.record` / `ReplayTOOL` (`on_miss='live'` splice, mutation isolation, `>10KB` compression) |
| `test_mcp.py` | `MCP` stdio (`shell=False` argv & shell string) and HTTP JSON-RPC transports, `headers`/`timeout`, `prefix=`, `isError=True` |
| `test_agent.py` | Governed write-ahead `AGENT` (`allow`, `policy`, `budget`, `checkpoint`, `decision=` resume, `tool_loop`), `protocol='auto'` fallback, `ReactAgent`, `ReflectAgent`, `PlanActAgent` |
| `test_delegate.py` | `DELEGATE` `handoff`, `dispatch`, and `broadcast` with `memory.copy()` variable/tombstone fidelity |
| `test_workflow.py` | `WORKFLOW` sequential steps, condition errors, `ok='auto'` / callable predicates, `previous_failed` branching, `while_` loops, persisted `{name}_log`, and suspend/resume |
| `test_chron.py` | Cron expression parser (`@daily` aliases, ranges, steps, OR-day semantics), `CHRON.tick()`, `fire()`, catch-up, and state persistence |
| `test_chat.py` | `CHAT` interactive loop, reverse-chronological multi-step `_extract_response`, `internal=True` filtering |
| `test_replay.py`, `test_eval.py` | Cross-primitive record/replay determinism and `Harness` (`strict=True` absorbed-error detection, partial `memory` capture) |
| `test_reference_plan_loop.py` | Reference plan-commit-reflect loop receipts, `{step_N_result}` resolution, approvals, and sub-run isolation |
| `test_util.py`, `test_this.py` | `EventStamp`, `hashify`, `valid_extract`, `render_template`, heap-address scrubbing, and `thoughtflow.this` |

---

### `tests/integration/` — Live Provider Smoke Suites (Opt-In)

Integration tests hit real external APIs or real wall-clock timers and are skipped unless explicitly enabled:

```bash
# Run live LLM, EMBED, and DM provider smoke tests (skips providers without keys in env):
THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_llm_providers.py \
  tests/integration/test_embed_providers.py \
  tests/integration/test_dm_providers.py -v

# Run live web search, scrape, and real-timer CHRON integration tests:
pytest tests/integration/test_search_providers.py \
  tests/integration/test_scrape.py \
  tests/integration/test_chron.py -v
```

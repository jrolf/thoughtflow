# `primitives/` — Canonical Per-Primitive Reference Specifications

> **Scope:** Complete, class-by-class reference specifications for every ThoughtFlow primitive (32 specifications across 7 architectural layers).
> **Read alongside:** [`README.md`](../README.md) · [`src/thoughtflow/README.md`](../src/thoughtflow/README.md) · [`docs/`](../docs/index.md)

---

## How to Use This Directory

Each file in `primitives/` documents **one exported class** on its own terms:
1. **Philosophy** — *why* the primitive exists and what boundary it draws against adjacent primitives.
2. **How It Works** — internal mechanics, wire protocols, event/variable writes on `MEMORY`, and failure semantics.
3. **Inputs & Configuration** — constructor parameters, methods, and defaults.
4. **Usage** — self-contained, idiomatic Python snippets.
5. **Relationship to Other Primitives** — how it composes across the stack.

---

## Index by Architectural Layer

### 1. Intelligence Layer (Stateless Model Clients)
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`LLM.md`](LLM.md) | `src/thoughtflow/llm.py`, `llm_chat.py` | Multi-provider text (`call`) & structured tool-call (`chat`) client with streaming, abort, caching, `llm.usage` ledger, `LLM.cassette()`, and `ReplayLLM` |
| [`EMBED.md`](EMBED.md) | `src/thoughtflow/embed.py` | Multi-provider single & batch vector embeddings, `cosine_similarity` / `cosine_retrieve` helpers, and `ReplayEMBED` |
| [`DM.md`](DM.md) | `src/thoughtflow/dm.py` | Multi-provider System-One decision models (`choice`, `noul`, `score`, `box`), normalized `confidence`/`margin`, `DM.from_llm()`, and `ReplayDM` |

### 2. State Layer
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`MEMORY.md`](MEMORY.md) | `src/thoughtflow/memory.py` | Event-sourced state container: causal `_seq`, `upsert()` & var metadata, `find_vars()`, `get_events(since=)`, `scope()`, `budget_tokens=`, `compact()`, `to_json(slim=True)`, `revision` & `merge()`, `suspend()`/`resolve_suspension()`, `emit()`, and exchange recordings |

### 3. Cognition Layer (`memory = thought(memory)`)
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`THOUGHT.md`](THOUGHT.md) | `src/thoughtflow/thought.py` | Atomic reasoning unit: prompt templates, `output_schema` & `reasoning`, `.run()`, schema dialect (`oneOf`, unions, `enum`), declarative/callable validation, retry policies, `visibility`, and `{name}_outcome` |
| [`DECIDE.md`](DECIDE.md) | `src/thoughtflow/thoughts/decide.py` | Bounded decisions over `LLM` or `DM`: categorical `choices` (+ `abstain=`), binary `choices=bool` (`noul`), rubric `levels` (`score`), batched `questions`, `{name}_source` provenance, and `min_confidence`/`min_margin` gating |
| [`PLAN.md`](PLAN.md) | `src/thoughtflow/thoughts/plan.py` | Structured multi-step sequential/parallel plan generation (`list[list[dict]]`) with `$step_N_result` references, `run_plan` executor, param schema validation, and `normalize_plan()` |

### 4. Operation Layer (`memory = action(memory, **kwargs)`)
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`ACTION.md`](ACTION.md) | `src/thoughtflow/action.py` | Base imperative side-effect wrapper with execution timing, `{name}_result` / `{name}_status` / `{name}_outcome` storage, and error containment |
| [`SAY.md`](SAY.md) · [`ASK.md`](ASK.md) · [`NOTIFY.md`](NOTIFY.md) | `actions/say.py`, `ask.py`, `notify.py` | User output, interactive input with validation, and console/webhook notifications |
| [`SEARCH.md`](SEARCH.md) · [`FETCH.md`](FETCH.md) · [`SCRAPE.md`](SCRAPE.md) · [`READ.md`](READ.md) | `actions/search.py`, `fetch.py`, `scrape.py`, `read_file.py` | Multi-provider web search, HTTP requests, HTML/Markdown/structured scraping, and local file reads |
| [`WRITE.md`](WRITE.md) · [`POST.md`](POST.md) | `actions/write_file.py`, `post.py` | File persistence and HTTP POST payloads |
| [`SLEEP.md`](SLEEP.md) · [`WAIT.md`](WAIT.md) · [`NOOP.md`](NOOP.md) | `actions/sleep.py`, `wait.py`, `noop.py` | Rate-limit pauses, condition polling, and explicit no-op steps |
| [`RUN.md`](RUN.md) · [`CALL.md`](CALL.md) | `actions/run.py`, `call.py` | Subprocess execution and arbitrary Python callable invocation |

### 5. Capability Layer (Model-Selectable Tools)
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`TOOL.md`](TOOL.md) | `src/thoughtflow/tool.py` | JSON-Schema tool wrapper with `needs_context=True`, `TOOL.from_action()`, and hermetic `record()` / `ReplayTOOL` (`on_miss='live'` splice) |
| [`MCP.md`](MCP.md) | `src/thoughtflow/mcp.py` | Zero-dependency Model Context Protocol client (`stdio` shell/argv + `http`, `headers`, `timeout`, `prefix=`, `isError` raising) |

### 6. Autonomy Layer (`memory = agent(memory)`)
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`AGENT.md`](AGENT.md) | `src/thoughtflow/agent.py` | Governed write-ahead native `LLM.chat()` tool loop (`allow`, `policy`, `budget`, `checkpoint`, `decision=` resume, `tool_loop` helper) + text-JSON fallback |
| [`ReactAgent.md`](ReactAgent.md) | `src/thoughtflow/agents/react.py` | Explicit `Thought:` / `Action:` / `Observation:` / `Final Answer:` text loop |
| [`ReflectAgent.md`](ReflectAgent.md) | `src/thoughtflow/agents/reflect.py` | Task-aware, negation-safe self-critique and iterative revision loop |
| [`PlanActAgent.md`](PlanActAgent.md) | `src/thoughtflow/agents/planact.py` | Plan-then-execute agent with bounded `max_replans` adaptive replanning and `{name}_outcome` |

### 7. Coordination & Orchestration Layers
| Specification | Source Module | Summary |
|---------------|---------------|---------|
| [`DELEGATE.md`](DELEGATE.md) | `src/thoughtflow/delegate.py` | Multi-agent routing (`handoff`, `dispatch`, `broadcast`, `dispatch_many`, and `map_thought`) over isolated `memory.copy()` clones |
| [`CHAT.md`](CHAT.md) | `src/thoughtflow/chat.py` | Interactive multi-turn terminal & notebook conversation loop |
| [`WORKFLOW.md`](WORKFLOW.md) | `src/thoughtflow/workflow.py` | Step pipelines with conditions, `ok=` checks, status routing, bounded `while_`, persisted `{name}_log`, and suspend/resume |
| [`CHRON.md`](CHRON.md) | `src/thoughtflow/chron.py` | Cron (`0 9 * * 1-5`, `@daily`) and interval scheduler supporting serverless `tick()` and background daemon loops |

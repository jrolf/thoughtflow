# DELEGATE

> Multi-agent coordination: handoff, dispatch, and broadcast.

## Philosophy

DELEGATE exists because single agents have limits. A triage agent may need to route to a specialist. A coordinator may need a researcher to gather facts and report back. Multiple agents may need to answer the same question in parallel for voting or ensemble. DELEGATE is the primitive that defines how agents pass work to other agents. It is not an agent itself — it is a coordinator that agents use.

DELEGATE supports three modes with different semantics. Handoff is fire-and-forget: the receiving agent gets a copy of memory and runs; the caller does not wait. Dispatch is request-response: the receiving agent runs, and its result is merged back into the caller's memory. Broadcast is fan-out: the same task goes to multiple agents, and results are collected. Memory isolation is preserved: DELEGATE always works with a copy of memory for the target agent, never mutating the original except when merging results back (dispatch and broadcast).

## How It Works

**Registration** — Pass either a list of agent instances (each with a `.name` attribute) or a `{name: callable}` dict (`DELEGATE(agents={'billing': fn, 'tech': agent})`) where any `memory -> memory` callable (`AGENT`, `WORKFLOW`, `THOUGHT`, or function) can act as a specialist. Unknown agent names raise `KeyError`.

**Memory copy** — `_copy_memory` delegates to `memory.copy()` (deep-copying events, scalar/collection variable values, descriptions, tombstones, and compressed objects) so the target agent receives an isolated, faithful snapshot of the caller's state without mutating the original `MEMORY` except when `dispatch`, `dispatch_many`, or `broadcast` merges results back.

**Handoff** — Copy memory, optionally add task as user message, run target agent on the copy. Log the delegation. Return the result memory (caller typically discards it). Original memory unchanged.

**Dispatch** — Copy memory, add task if provided, run target agent, and capture a structured outcome (`ok`, `result`, `error`, `usage`, `messages`). Merge `{agent_name}_dispatch_result` and `{agent_name}_dispatch_outcome` into original memory, plus optional `merge_vars` (`True` or iterable of keys) and `merge_msgs=True` delta merge-back. Return original memory.

**Broadcast & `dispatch_many`** — `broadcast(memory, task=None, agent_names=None, parallel=False, max_workers=None)` fans one task out across specialists (sequentially or in parallel via `ThreadPoolExecutor`) and writes `{delegate_name}_broadcast_results` plus `{delegate_name}_broadcast_outcomes`. `dispatch_many(memory, assignments, parallel=False, max_workers=None)` fans distinct `(agent_name, task)` assignments out over isolated `MEMORY` copies and writes `{delegate_name}_dispatch_many_results` and `{delegate_name}_dispatch_many_outcomes`.

**`map_thought` combinator** — `map_thought(thought, memory, items=None, n=None, var_name='item', parallel=True, max_workers=None)` (exported at `thoughtflow.map_thought` and `thoughtflow.delegate.map_thought`) runs one `THOUGHT` / `DECIDE` / `PLAN` / callable across `items` or `n` samples on isolated `MEMORY` copies and returns `{results, outcomes, usage, memories}` in deterministic input order.

**Logging** — Each delegation appends to `delegation_log` with stamp, mode, target, task, `ok`, `error`, and `usage`.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `agents` | List of agent instances (each with `.name`) or `{name: callable}` dict | `[]` |
| `name` | Identifier for this coordinator | `"delegate"` |

Methods:

| Method | Parameters | Description |
|--------|-------------|-------------|
| `handoff` | `memory, agent_name, task=None` | One-way transfer; no result merged |
| `dispatch` | `memory, agent_name, task=None, merge_vars=False, merge_msgs=False` | Request-response; writes `{agent_name}_dispatch_result` and `{agent_name}_dispatch_outcome` |
| `broadcast` | `memory, task=None, agent_names=None, parallel=False, max_workers=None` | Fan-out same task; writes `{name}_broadcast_results` and `{name}_broadcast_outcomes` |
| `dispatch_many` | `memory, assignments, parallel=False, max_workers=None` | Fan-out distinct `(agent, task)` pairs; writes `{name}_dispatch_many_results` and `{name}_dispatch_many_outcomes` |

## Usage

```python
from thoughtflow import LLM, MEMORY, AGENT, DELEGATE

researcher = AGENT(llm=llm, tools=[search_tool], name="researcher")
writer = AGENT(llm=llm, name="writer")
delegate = DELEGATE(agents=[researcher, writer])

# Dispatch: send to researcher, get result back
memory = delegate.dispatch(memory, "researcher", "Find info on X")
result = memory.get_var("researcher_dispatch_result")

# Handoff: pass to writer, don't wait
delegate.handoff(memory, "writer", "Write a summary")

# Broadcast: ask both the same question
memory = delegate.broadcast(memory, "Summarize your findings")
results = memory.get_var("delegate_broadcast_results")  # {agent_name: result}
```

## Relationship to Other Primitives

- **AGENT** — DELEGATE coordinates agents. It looks them up by name and calls them with a memory copy. Agents are the workers; DELEGATE is the router.
- **MEMORY** — The vehicle for passing state. DELEGATE copies memory for targets and merges results back for dispatch/broadcast.
- **WORKFLOW** — WORKFLOW can include DELEGATE as a step. A workflow step might call `delegate.dispatch(memory, "researcher", task)`.

## Considerations for Future Development

- Context filter: pass a subset of memory (e.g., last N messages) instead of full copy.
- Timeout for dispatch to avoid hanging on slow agents.
- Delegation chain tracing (A dispatched to B, B dispatched to C).

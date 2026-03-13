# DELEGATE

> Multi-agent coordination: handoff, dispatch, and broadcast.

## Philosophy

DELEGATE exists because single agents have limits. A triage agent may need to route to a specialist. A coordinator may need a researcher to gather facts and report back. Multiple agents may need to answer the same question in parallel for voting or ensemble. DELEGATE is the primitive that defines how agents pass work to other agents. It is not an agent itself — it is a coordinator that agents use.

DELEGATE supports three modes with different semantics. Handoff is fire-and-forget: the receiving agent gets a copy of memory and runs; the caller does not wait. Dispatch is request-response: the receiving agent runs, and its result is merged back into the caller's memory. Broadcast is fan-out: the same task goes to multiple agents, and results are collected. Memory isolation is preserved: DELEGATE always works with a copy of memory for the target agent, never mutating the original except when merging results back (dispatch and broadcast).

## How It Works

**Registration** — Pass a list of agents to the constructor. Each must have a `name` attribute. DELEGATE builds a `name -> agent` lookup. Unknown agent names raise `KeyError`.

**Memory copy** — `_copy_memory` creates a lightweight copy: new MEMORY instance, same messages and variables. Not a deep copy; nested objects are shared. The copy is passed to the target agent so the original is unchanged (except for merged results).

**Handoff** — Copy memory, optionally add task as user message, run target agent on the copy. Log the delegation. Return the result memory (caller typically discards it). Original memory unchanged.

**Dispatch** — Copy memory, add task if provided, run target agent. Extract `{agent_name}_result` from the result memory. Merge into original memory as `{agent_name}_dispatch_result`. Return original memory.

**Broadcast** — For each target agent (or all if none specified): copy memory, add task, run agent, extract result. Collect results in a dict. Store as `{delegate_name}_broadcast_results` in original memory. Return original memory.

**Logging** — Each delegation appends to `delegation_log` with stamp, mode, target, task, and whether a result was produced.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| agents | List of agent instances (each with `.name`) | [] |
| name | Identifier for this coordinator | "delegate" |

Methods:

| Method | Parameters | Description |
|--------|-------------|-------------|
| handoff | memory, agent_name, task=None | One-way transfer; no result merged |
| dispatch | memory, agent_name, task=None | Request-response; result in `{agent_name}_dispatch_result` |
| broadcast | memory, task=None, agent_names=None | Fan-out; results in `{name}_broadcast_results` |

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
- Parallel execution for broadcast (currently sequential).
- Timeout for dispatch to avoid hanging on slow agents.
- Delegation chain tracing (A dispatched to B, B dispatched to C).

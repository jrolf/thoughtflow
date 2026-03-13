# Thoughtflow: New Primitives Strategy

This document defines the next wave of primitives for Thoughtflow. Its purpose is to establish precise conceptual boundaries between each new primitive, explain how each one relates to the existing foundation (LLM, MEMORY, THOUGHT, ACTION, CHAT), and lay out the implementation sequence so that each primitive can build on the ones before it.

The guiding constraint throughout: **Thoughtflow has zero dependencies outside the Python standard library.** Every primitive below must be implementable with `urllib`, `json`, `subprocess`, `socket`, and the rest of the stdlib. Provider-specific SDKs remain optional extras, never requirements.

---

## Existing Foundation (for reference)

Before defining anything new, it helps to name exactly what already exists and what role each piece plays. The new primitives must draw clean lines against these.

| Primitive | Role | Core Contract |
|-----------|------|---------------|
| **LLM** | Unified interface for calling language models (text generation) | `response = llm.call(msg_list, params)` |
| **MEMORY** | Event-sourced state container (messages, variables, logs) | `memory.add_msg(...)`, `memory.set_var(...)`, `memory.get_var(...)` |
| **THOUGHT** | Atomic unit of cognition: prompt + context + LLM + parsing + validation | `memory = thought(memory)` |
| **DECIDE** | Constrained choice from a finite set (subclass of THOUGHT) | `memory = decide(memory)` |
| **PLAN** | Multi-step plan generation (subclass of THOUGHT) | `memory = plan(memory)` |
| **ACTION** | Imperative operation wrapper with logging, timing, and result storage | `memory = action(memory, **kwargs)` |
| **CHAT** | Interactive human-in-the-loop conversation wrapper | `chat.run()` or `response = chat.turn(input)` |

The fundamental Thoughtflow contract is: **`memory = primitive(memory)`**. New primitives should preserve this wherever it makes sense.

---

## New Primitives

### 1. EMBED

**What it is.** EMBED is the embedding counterpart to LLM. Where LLM sends messages to a text generation endpoint and returns a completion, EMBED sends text to an embedding endpoint and returns a vector (list of floats). It follows the same multi-provider pattern as LLM — a single class that routes to OpenAI, Groq, Anthropic, Ollama, Gemini, or OpenRouter based on a `model_id` string like `"openai:text-embedding-3-small"` or `"ollama:nomic-embed-text"`.

**Why it is distinct from LLM.** LLM calls text generation APIs. EMBED calls embedding APIs. The endpoints, payloads, and response shapes are completely different. Conflating them into a single class would muddy the interface and force users to remember which methods apply to which mode. Keeping them separate preserves the principle that each primitive has one clear job.

**Relationship to existing primitives.** EMBED stands beside LLM as a sibling. It does not depend on MEMORY, THOUGHT, or ACTION. It is a low-level building block that higher-level code (such as semantic memory, retrieval, or similarity-based routing) can compose with freely.

**Core contract:**

```python
embed = EMBED("openai:text-embedding-3-small", key="...")
vector = embed.call("Some text to embed")
vectors = embed.call(["Text one", "Text two", "Text three"])
```

**Key design points:**

- Constructor mirrors LLM: `EMBED(model_id, key, secret)`
- `.call()` accepts a single string or a list of strings, returns a single vector or a list of vectors
- Provider routing by prefix, same as LLM (`openai:`, `ollama:`, etc.)
- Ollama support for local embedding models
- No dependencies beyond `urllib` and `json`
- Dimensions, model metadata, and token counts available on the response where the provider supplies them

---

### 2. TOOL

**What it is.** TOOL is a callable capability that is exposed to an LLM for selection. It wraps a function (or an ACTION) and adds a **schema** — a name, a description, and a parameter specification — that can be formatted into the JSON structure that LLM providers expect for function calling / tool use. The LLM sees the schema, decides whether and when to call the tool, and generates the arguments. The framework executes the tool and returns the result to the LLM.

**The precise boundary between TOOL and ACTION.** This is the single most important conceptual line to draw cleanly:

- **ACTION** is imperative. Your code calls it. The LLM never sees it, never selects it, never generates arguments for it. ACTION is a verb that the developer (or the agent's orchestration logic) invokes directly: `memory = search(memory, query="...")`. ACTIONs are the hands and feet of the system.

- **TOOL** is declarative. The LLM selects it. TOOL exists primarily as a **schema that the LLM can reason about**, plus an execution function that runs when the LLM chooses it. The developer does not call a TOOL directly in normal usage — the agent loop does, in response to the LLM's tool-call request.

The relationship between them: a TOOL *can* wrap an ACTION as its execution function, but it does not have to. Any callable works. An ACTION can be **promoted** to a TOOL by attaching a schema. Conversely, a TOOL can exist without an ACTION underneath — a plain function is fine. Think of ACTION as the execution layer and TOOL as the selection layer.

**Core contract:**

```python
# From a plain function
search_tool = TOOL(
    name="web_search",
    description="Search the web for current information.",
    parameters={"query": {"type": "string", "description": "Search query"}},
    fn=my_search_function,
)

# From an existing ACTION
search_tool = TOOL.from_action(
    SEARCH,
    description="Search the web for current information.",
    parameters={"query": {"type": "string", "description": "Search query"}},
)

# Schema generation for LLM providers
schema = search_tool.to_schema()  # returns provider-ready JSON dict

# Execution (normally called by the agent loop, not by the user)
result = search_tool(arguments={"query": "latest news"})
```

**Key design points:**

- `TOOL(name, description, parameters, fn)` — minimal required surface
- `.to_schema()` returns the dict structure that LLM providers expect (OpenAI function-calling format as the canonical shape, with adapter methods for other providers if needed)
- `.from_action(action, description, parameters)` — promote an ACTION to a TOOL
- Execution is traceable (integrates with the trace/events system's existing `TOOL_CALL` / `TOOL_RESULT` event types)
- Tools are stubbable: a `TOOL(... fn=mock_fn)` supports deterministic testing, consistent with Thoughtflow's testing philosophy

---

### 3. MCP

**What it is.** MCP is a client that connects to one or more Model Context Protocol servers and discovers their available tools. It speaks the MCP protocol (JSON-RPC over stdio or HTTP+SSE) using only the Python standard library, and it returns TOOL instances that integrate seamlessly with the rest of Thoughtflow.

**Why it is a primitive and not a library integration.** MCP is not a wrapper around someone else's SDK. It is a protocol client built from scratch with `subprocess` (for stdio transport) and `urllib` / `http.client` (for HTTP+SSE transport). This is deliberate: Thoughtflow has no dependencies, and MCP's wire protocol (JSON-RPC 2.0) is simple enough to implement cleanly with stdlib. The result is a first-class Thoughtflow citizen, not an adapter around a third-party package.

**Relationship to TOOL.** MCP's output is TOOLs. When you connect to an MCP server and call `.list_tools()`, you get back a list of TOOL instances with their schemas already populated. These TOOLs can be handed directly to an AGENT. MCP is the discovery and transport layer; TOOL is the unit of capability.

**Core contract:**

```python
# Connect to a local MCP server via stdio
mcp = MCP("npx -y @modelcontextprotocol/server-filesystem /tmp")

# Connect to a remote MCP server via HTTP+SSE
mcp = MCP("https://my-mcp-server.example.com/sse")

# Discover tools
tools = mcp.list_tools()  # returns list[TOOL]

# Use those tools with an agent (see AGENT below)
agent = AGENT(llm=llm, tools=tools, memory=memory)

# Direct tool invocation (if needed)
result = mcp.call_tool("read_file", {"path": "/tmp/notes.txt"})

# Clean shutdown
mcp.close()

# Context manager support
with MCP("npx -y @modelcontextprotocol/server-filesystem /tmp") as mcp:
    tools = mcp.list_tools()
```

**Key design points:**

- Single constructor that auto-detects transport: if the argument starts with `http://` or `https://`, use HTTP+SSE; otherwise, treat it as a shell command and use stdio via `subprocess`
- `.list_tools()` returns TOOL instances (not raw dicts) — seamless integration
- `.call_tool(name, arguments)` for direct invocation
- `.list_resources()` and `.read_resource()` for MCP resource access
- Context manager (`with`) support for clean subprocess / connection lifecycle
- JSON-RPC 2.0 implementation is internal and minimal — just enough to speak the protocol
- No dependency on the `mcp` pip package or any other third-party library

---

### 4. AGENT

**What it is.** AGENT is the autonomous execution loop — the primitive that makes an LLM into an agent. It combines an LLM, a set of TOOLs, and a MEMORY, and runs the cycle: **call the LLM → the LLM may request tool calls → execute those tools → feed results back to the LLM → repeat until the LLM produces a final response or a limit is reached.** This is the core "agentic loop" that every agent framework provides in some form.

**Relationship to existing primitives.** AGENT is the orchestrator that sits above LLM, TOOL, and MEMORY. It does not replace THOUGHT — a THOUGHT is an atomic cognitive step (prompt + parse + validate), while an AGENT is a *loop* that may execute many such steps autonomously. AGENT also does not replace CHAT — CHAT is an interactive human-in-the-loop wrapper, while AGENT runs autonomously. In practice, CHAT could wrap an AGENT to create an interactive agent session, just as it currently wraps a THOUGHT.

**Superclass and subclasses.** AGENT is the base class that implements the generic tool-use loop. Subclasses implement specific agentic methodologies:

- **AGENT** (base) — The vanilla tool-use loop. Call LLM with tools, execute tool calls, feed results back, repeat. No special prompting strategy beyond what the user provides.

- **ReactAgent** (subclass) — Implements the Reason + Act methodology. Each iteration explicitly structures the LLM's output into Thought → Action → Observation steps. The system prompt and parsing enforce this structure.

- **ReflectAgent** (subclass) — After producing a response, the agent critiques its own output and optionally revises it. Useful for self-correction loops.

- **PlanActAgent** (subclass) — The agent first generates a plan (using PLAN-like logic), then executes each step, checking progress and re-planning as needed. Plan-then-execute with adaptive replanning.

Each subclass overrides specific parts of the loop (how prompts are structured, how iterations are parsed, when to stop) while inheriting the tool execution, memory management, and tracing infrastructure from the base AGENT.

**Core contract:**

```python
# Base agent
agent = AGENT(
    llm=llm,
    tools=[search_tool, read_tool, write_tool],
    system_prompt="You are a research assistant.",
    max_iterations=10,
)
memory = agent(memory)  # runs the full loop, returns updated memory

# ReAct agent
agent = ReactAgent(
    llm=llm,
    tools=[search_tool, calculator_tool],
    system_prompt="You are a problem-solving assistant.",
    max_iterations=5,
)
memory = agent(memory)

# Works with CHAT for interactive use
chat = CHAT(agent)
chat.run()
```

**Key design points:**

- Preserves the Thoughtflow contract: `memory = agent(memory)`
- Base AGENT implements: LLM call with tool schemas, tool-call parsing, tool execution, result injection, iteration control
- Subclasses override: prompt construction strategy, response parsing, stop conditions, inter-step logic
- `max_iterations` prevents runaway loops
- `on_tool_call` hook for human-in-the-loop approval patterns
- Each iteration is traced via the existing trace/events system
- Tools can come from direct TOOL instances, from MCP, or from a mix of both

---

### 5. DELEGATE

**What it is.** DELEGATE is the primitive for multi-agent coordination. It defines how one agent transfers work to another agent. There are fundamentally different delegation mechanics, and DELEGATE needs to represent them cleanly without pretending they are the same thing.

The core delegation patterns:

- **Handoff** — Agent A transfers full control to Agent B. Agent A does not expect a response and does not resume. The conversation or task moves permanently to Agent B. This is routing: a triage agent hands off to a specialist.

- **Dispatch** — Agent A sends a sub-task to Agent B and waits for the result. Agent B completes the task and returns a response. Agent A continues processing with that response. This is delegation in the traditional sense: "go do this and report back."

- **Broadcast** — Agent A sends the same task to multiple agents (B, C, D) and collects their responses. This is fan-out: parallel research, voting, or ensemble patterns.

**Relationship to AGENT.** DELEGATE operates *between* AGENTs. It is not itself an agent — it is a coordination mechanism. A DELEGATE describes the relationship and the protocol (handoff vs. dispatch vs. broadcast), while the AGENTs do the actual work. DELEGATE transfers MEMORY (or a subset of it) from one agent to another, which is the natural Thoughtflow way of passing state.

**Core contract:**

```python
# Handoff: triage agent routes to specialist, does not resume
handoff = DELEGATE(
    source=triage_agent,
    target=specialist_agent,
    mode="handoff",
    context_filter=lambda memory: memory.get_msgs(last_n=5),  # what to pass
)

# Dispatch: research agent sends sub-task, waits for result
dispatch = DELEGATE(
    source=coordinator_agent,
    target=research_agent,
    mode="dispatch",
    task_prompt="Summarize the latest findings on {topic}.",
)

# Using delegates within an agent's workflow
result_memory = dispatch(source_memory)
```

**Key design points:**

- Three modes: `handoff`, `dispatch`, `broadcast`
- MEMORY is the vehicle for passing state between agents — consistent with Thoughtflow's architecture
- `context_filter` controls what subset of memory is transferred (full memory, last N messages, specific variables, etc.)
- For `dispatch`, the result from the target agent is injected back into the source agent's memory
- For `broadcast`, results from all target agents are collected and merged
- Traced as first-class events in the session
- Composable: delegates can be used inside WORKFLOW (see below) or called directly

---

### 6. WORKFLOW

**What it is.** WORKFLOW is a lightweight orchestration primitive for composing THOUGHTs, ACTIONs, AGENTs, and DELEGATEs into non-linear execution flows. It supports sequential steps, conditional branching, parallel execution, and loops with exit conditions — but it does all of this in plain Python, not through a graph DSL or YAML configuration.

**Why this is a primitive and not just "use Python."** You can absolutely build any workflow with plain Python `if/else`, `for` loops, and function calls — and Thoughtflow's philosophy encourages that for simple cases. WORKFLOW earns its place as a primitive because it adds three things that raw Python does not give you for free: **(1)** automatic tracing of every step in the workflow, **(2)** the ability to serialize, inspect, and replay a workflow's execution, and **(3)** a consistent interface for defining reusable, composable workflow patterns that other developers can read and understand without reverse-engineering imperative code.

**Relationship to AGENT and PLAN.** PLAN generates a plan (a data structure describing steps). AGENT executes an autonomous loop. WORKFLOW is the connective tissue that says "run this THOUGHT, then if the result is X, run this AGENT, otherwise run that ACTION, then collect results and run this final THOUGHT." It is the explicit orchestrator — the conductor of the orchestra, where THOUGHTs, ACTIONs, and AGENTs are the musicians.

**Core contract:**

```python
workflow = WORKFLOW(name="research_and_write")

# Define steps
workflow.step("gather", research_agent)
workflow.step("outline", outline_thought, after="gather")
workflow.step("draft", writing_agent, after="outline")
workflow.step("review", review_thought, after="draft")
workflow.step(
    "revise_or_publish",
    condition=lambda memory: memory.get_var("review_passed"),
    if_true=publish_action,
    if_false=revision_agent,
    after="review",
)

# Run
memory = workflow(memory)
```

**Key design points:**

- Steps are named and explicitly ordered (via `after=` dependencies), not implicitly sequenced by definition order
- Conditional branching via `condition=` lambda on a step
- Parallel steps: steps with the same `after=` dependency can run concurrently
- Loop support: a step can reference an earlier step as its `after=`, creating a cycle with an exit condition
- Every step execution is traced
- The entire workflow is serializable and inspectable
- Preserves `memory = workflow(memory)` contract
- Intentionally lightweight — this is not a full DAG engine, it is a thin orchestration layer that stays Pythonic

---

## Features (Non-Primitive Enhancements)

The following are not new classes or primitives. They are capabilities that need to be woven into existing and new primitives as cross-cutting features.

### Streaming

Streaming support means the LLM class can return tokens incrementally rather than waiting for the full response. This needs to propagate upward: LLM streams tokens, THOUGHT can optionally stream its output, AGENT can stream intermediate steps, and CHAT can display streaming responses.

**Implementation approach.** The LLM `.call()` method gains a `stream=True` parameter. When enabled, it returns a generator (or iterator) that yields chunks as they arrive. A separate `.stream()` convenience method may also be provided. For tool-call responses during streaming, the stream collects tool-call fragments and yields a complete tool-call object once assembled.

**Scope of impact:** LLM (primary), THOUGHT (optional passthrough), AGENT (intermediate step streaming), CHAT (display streaming).

### Structured Output

Structured output means the LLM can be constrained to produce a response matching a specific JSON schema, using the provider's native structured output API (OpenAI's `response_format`, Anthropic's tool-use-as-schema, etc.) rather than relying on post-hoc text parsing.

**Implementation approach.** The LLM `.call()` method gains an `output_schema=` parameter that accepts a dict (JSON Schema). When provided, the LLM adapter formats it according to the provider's native structured output mechanism. THOUGHT gains an `output_schema=` config option that passes through to the LLM call and bypasses the text-based `valid_extract` parsing, since the response is guaranteed to conform. For providers that do not support native structured output, the system falls back to prompt-based enforcement and `valid_extract`.

**Scope of impact:** LLM (primary — schema formatting per provider), THOUGHT (config option + parsing bypass).

---

## Implementation Sequence

The primitives build on each other. The sequence below ensures that each primitive has its dependencies in place before implementation begins.

```
Phase 1: Independent foundations
  ├── EMBED .............. (no dependencies on other new primitives)
  └── TOOL ............... (clarifies ACTION boundary; needed by everything above)

Phase 2: Connectivity
  └── MCP ................ (depends on TOOL — MCP returns TOOLs)

Phase 3: Autonomy
  └── AGENT .............. (depends on TOOL — the agent loop uses tools)
      ├── ReactAgent
      ├── ReflectAgent
      └── PlanActAgent

Phase 4: Coordination
  └── DELEGATE ........... (depends on AGENT — coordinates between agents)

Phase 5: Orchestration
  └── WORKFLOW ............ (depends on AGENT, DELEGATE, THOUGHT, ACTION)

Features (woven in progressively):
  ├── Structured Output .. (LLM + THOUGHT — can start in Phase 1)
  └── Streaming .......... (LLM + THOUGHT + AGENT + CHAT — starts Phase 1, widens with each phase)
```

**Why this order:**

1. **EMBED** and **TOOL** are independent of each other and of everything above them. They can be built in parallel. EMBED is a sibling to LLM. TOOL clarifies the ACTION boundary and establishes the schema layer that MCP and AGENT both need.

2. **MCP** needs TOOL to exist, because its output is TOOL instances. It cannot be built until the TOOL contract is stable.

3. **AGENT** needs TOOL because the agentic loop is fundamentally about the LLM selecting and invoking tools. Without TOOL, there is no agent loop — just a THOUGHT with extra steps.

4. **DELEGATE** needs AGENT because delegation is a relationship between agents. You cannot define handoff or dispatch semantics without the agents that participate in them.

5. **WORKFLOW** sits at the top because it orchestrates everything: THOUGHTs, ACTIONs, AGENTs, and DELEGATEs. It is the most dependent and therefore the last to implement.

6. **Streaming** and **Structured Output** are features that start at the LLM layer and propagate upward. They can begin implementation in Phase 1 (LLM changes) and widen as each new primitive is built. The LLM-level changes for structured output in particular are a natural companion to the TOOL work, since tool schemas and structured output schemas share the same JSON Schema format.

---

## Summary Table

| # | Primitive | Type | Depends On | What It Does |
|---|-----------|------|------------|--------------|
| 1 | **EMBED** | Class | LLM pattern (sibling) | Text embedding via multi-provider API |
| 2 | **TOOL** | Class | ACTION (extends concept) | LLM-selectable capability with schema |
| 3 | **MCP** | Class | TOOL | Protocol client for MCP server tool discovery |
| 4 | **AGENT** | Class + subclasses | LLM, TOOL, MEMORY | Autonomous tool-use loop |
| 5 | **DELEGATE** | Class | AGENT, MEMORY | Multi-agent coordination (handoff / dispatch / broadcast) |
| 6 | **WORKFLOW** | Class | All of the above | Lightweight orchestration of steps |
| — | Streaming | Feature | LLM (primary) | Token-by-token LLM output |
| — | Structured Output | Feature | LLM, THOUGHT | Provider-native schema enforcement |

# Agent

AGENT is the autonomous execution loop — the primitive that turns an LLM into an agent. It combines an LLM, a list of TOOLs, and a MEMORY, and runs the cycle: call the LLM, execute any tools it requests, feed the results back, repeat until the LLM produces a final answer.

---

## The Contract

Like every ThoughtFlow primitive, AGENT honors the universal contract:

```python
memory = agent(memory)
```

The agent reads the conversation from MEMORY, runs its loop, and returns the same MEMORY with the full interaction history appended. No hidden state, no separate session object.

---

## Basic Usage

```python
from thoughtflow import LLM, MEMORY, TOOL, AGENT

llm = LLM("openai:gpt-4o", key="sk-...")

weather_tool = TOOL(
    name="get_weather",
    description="Get the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
        },
        "required": ["city"],
    },
    fn=lambda city: {"city": city, "temp": 22, "units": "celsius"},
)

agent = AGENT(
    llm=llm,
    tools=[weather_tool],
    system_prompt="You are a helpful weather assistant.",
    max_iterations=5,
)

memory = MEMORY()
memory.add_msg("user", "What's the weather in Paris?")
memory = agent(memory)

print(memory.last_asst_msg(content_only=True))
```

The final response is added to memory as an `assistant` message and also stored in the variable `{name}_result` (here: `agent_result`).

---

## The Tool Loop

Each iteration of the loop:

1. **Build messages** — system prompt plus conversation history from memory.
2. **Call the LLM** with the tool schemas (`tools=[t.to_schema() for t in tools]`).
3. **Parse tool calls** from the response. The LLM proposes calls as JSON — `{"tool_calls": [...]}`, `{"tool_call": {...}}`, or a single `{"name": ..., "arguments": ...}`.
4. **Execute each tool** and record the interaction in memory: the request as an `action` message, the output as a `result` message.
5. **Repeat** until the LLM responds without tool calls (the final answer) or `max_iterations` is reached.

`max_iterations` (default 10) is the safety valve against runaway loops. When it is hit without a final answer, the agent logs the fact and returns the memory as-is.

The `action` and `result` roles are ThoughtFlow-internal; the LLM translates them to each provider's native role strings at the API boundary. See [LLM — Role Mapping](llm.md#role-mapping).

---

## The on_tool_call Hook

Pass `on_tool_call` to observe or veto tool executions. It receives `(tool_name, arguments)` before each execution; returning `False` blocks the call.

```python
def guard(tool_name, arguments):
    print("Agent wants to call {} with {}".format(tool_name, arguments))
    return tool_name != "delete_database"

agent = AGENT(llm=llm, tools=tools, on_tool_call=guard)
```

This is the natural place for approval gates, logging, and rate limits.

---

## LLM_ROLES Filtering

MEMORY can hold many role types — reflections, logs, queries — but only conversation-relevant roles should reach the LLM. The class attribute `LLM_ROLES` defines the filter:

```python
class AGENT:
    LLM_ROLES = {'user', 'assistant', 'system', 'action', 'result'}
```

When the agent builds messages, anything outside this set is omitted. Subclass and override `LLM_ROLES` to forward additional roles.

---

## Methodology Subclasses

Three subclasses override parts of the loop to implement specific agentic methodologies. All keep the `memory = agent(memory)` contract.

### ReactAgent

Reason + Act. Instead of the function-calling API, the LLM is prompted to emit explicit `Thought:` / `Action:` / `Action Input:` steps, observations are fed back as messages, and the loop ends on `Final Answer:`. The full reasoning trace lands in memory.

```python
from thoughtflow import ReactAgent

agent = ReactAgent(llm=llm, tools=[search_tool, calculator_tool])
memory = MEMORY()
memory.add_msg("user", "What is 23 * 47?")
memory = agent(memory)
```

### ReflectAgent

Generate, critique, revise. After the base loop produces a response, the agent critiques it with a separate LLM call and revises until the critique approves or `max_revisions` (default 2) is exhausted. Useful when quality matters more than latency.

```python
from thoughtflow import ReflectAgent

agent = ReflectAgent(llm=llm, system_prompt="You are a careful writer.", max_revisions=2)
memory = MEMORY()
memory.add_msg("user", "Write a haiku about programming.")
memory = agent(memory)
```

### PlanActAgent

Plan, then execute. The LLM first generates a structured plan (a JSON list of steps, each naming a tool and its arguments), then the agent executes the steps in order. If a step fails and `replan_on_failure` is True (the default), it regenerates a plan for the remaining work, and finishes with an LLM-written summary.

```python
from thoughtflow import PlanActAgent

agent = PlanActAgent(llm=llm, tools=[search_tool, write_tool])
memory = MEMORY()
memory.add_msg("user", "Research Python frameworks and write a summary.")
memory = agent(memory)
```

---

## Design Philosophy

- **One contract**: `memory = agent(memory)`, same as every other primitive
- **Visible history**: every tool request and result is an event in memory
- **Bounded**: `max_iterations` makes runaway loops impossible
- **Hookable**: `on_tool_call` puts a human (or policy) in the loop

For the complete API reference, see [primitives/AGENT.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/AGENT.md).

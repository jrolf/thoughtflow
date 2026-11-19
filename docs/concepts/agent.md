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

## The Tool Loop: Native Write-Ahead vs Text Fallback

`AGENT` supports two execution protocols (`protocol="auto"` by default):

### 1. Native Write-Ahead Protocol (`openai`, `openrouter`, `groq`, or custom `.chat()` LLMs)

When the `LLM` supports `chat()`, `AGENT` (and the functional `tool_loop(memory, llm, tools, ...)` helper) runs a durable, governed write-ahead loop:

1. **Build OpenAI messages** via `memory.get_llm_msgs(format="openai", merge_augments=self.merge_augments)`.
2. **Call `llm.chat(messages, tools=...)`** to obtain native `tool_calls` with stable IDs and usage metrics.
3. **Write-ahead persist** — write the `assistant` message with its `tool_calls` to `MEMORY` *before* any tool executes, and fire `checkpoint(memory)` if configured.
4. **Govern & execute** — check `allow=[...]`, `on_tool_call`, `policy` (`"allow"`, `"deny"`, `"approve"`, `"approve_over"`, or `callable(name, args)`), and `budget` (`max_model_calls`, `max_tool_calls`, `max_tokens`). Every `tool_call_id` receives a `role="tool"` answer (even when vetoed, unknown, or budget-halted) and triggers `checkpoint(memory)`.
5. **Suspend & resume** — if a call requires approval, `AGENT` calls `memory.suspend(...)` and returns with `{name}_status == "suspended"`. Rehydrate the `MEMORY` later and call `agent(memory, decision={"approve": True})` to resume directly from the unanswered `tool_calls` without re-running completed tools.
6. **Outcome recording** — stores `{name}_status` (`"final"`, `"suspended"`, `"max_iterations"`, `"budget_exhausted"`, `"vetoed"`, or `"error"`) and `{name}_outcome` (`ok`, `model_calls`, `tool_calls`, token counts, `vetoed`).

### 2. Text-JSON Fallback Protocol (`anthropic`, `gemini`, `ollama`, or `call()`-only mocks)

When the `LLM` does not support `LLM.chat()`, `AGENT` automatically runs the text-JSON loop: calling `llm.call()`, parsing JSON tool-call blocks, and recording interactions under `action` and `result` roles (translated at the provider boundary via `PROVIDER_ROLE_MAP`).

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

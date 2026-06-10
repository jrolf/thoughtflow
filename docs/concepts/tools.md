# Tools

A TOOL is a capability the LLM can choose to use. It wraps a callable and attaches a schema — name, description, parameter spec — so the model can discover it, reason about when to use it, and generate correct arguments. The agent loop executes the tool on the model's behalf and feeds the result back.

---

## TOOL vs ACTION: The Boundary

ThoughtFlow draws one line very deliberately:

- **ACTION is imperative.** Your code calls it. The LLM never sees it, never selects it, never generates arguments for it. `memory = search(memory, query="...")` — ACTIONs are the hands and feet of the system, invoked by the developer or by orchestration logic.

- **TOOL is declarative.** The LLM selects it. A TOOL exists primarily as a schema the model can reason about, plus an execution function that runs when the model chooses it. In normal usage you never call a TOOL yourself — the agent loop does, in response to the LLM's tool-call request.

The two layers compose: a TOOL *can* wrap an ACTION as its execution function, but any callable works. Think of ACTION as the execution layer and TOOL as the selection layer. Who decides to invoke it — your code or the model — is what determines which primitive you need.

---

## Creating a TOOL from a Function

```python
from thoughtflow import TOOL

def get_weather(city, units="celsius"):
    # Real implementation would call a weather API
    return {"city": city, "temp": 22, "units": units}

weather_tool = TOOL(
    name="get_weather",
    description="Get the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
            "units": {"type": "string", "description": "celsius or fahrenheit"},
        },
        "required": ["city"],
    },
    fn=get_weather,
)
```

`parameters` is a JSON Schema dict — the same format providers expect in their function-calling APIs. For simple cases you can pass a flat dict of property definitions and TOOL wraps it in `{"type": "object", "properties": ...}` automatically.

`tool.to_schema()` returns the OpenAI function-calling format, which the AGENT uses as the canonical shape when building the tools array for an LLM call.

---

## Giving Tools to an AGENT

```python
from thoughtflow import LLM, MEMORY, AGENT

llm = LLM("openai:gpt-4o", key="sk-...")

agent = AGENT(
    llm=llm,
    tools=[weather_tool],
    system_prompt="You are a helpful weather assistant.",
)

memory = MEMORY()
memory.add_msg("user", "How warm is it in Paris right now?")
memory = agent(memory)

print(memory.last_asst_msg(content_only=True))
```

The agent sends the schema to the LLM, the LLM decides to call `get_weather` with `{"city": "Paris"}`, the agent executes the function and feeds the result back, and the LLM writes its final answer from the result. The whole exchange is recorded in memory as `action` and `result` events.

When the LLM provides arguments, they are unpacked as keyword arguments to your function — so the function signature should match the schema's property names.

---

## Promoting an ACTION to a TOOL

When you already have an ACTION and want the LLM to be able to select it, promote it with `TOOL.from_action()`. ACTION carries no schema, so you supply the description and parameters:

```python
from thoughtflow import ACTION, TOOL

search = ACTION(name="search", fn=search_fn)

search_tool = TOOL.from_action(
    search,
    description="Search the web for current information.",
    parameters={"query": {"type": "string", "description": "Search query"}},
)
```

One subtlety: ACTION functions receive `(memory, **kwargs)`, but a TOOL's function receives only the keyword arguments the LLM generated. `from_action()` bridges this by passing `None` for the memory argument — the agent loop owns memory integration, not the tool. If your ACTION function genuinely needs the memory, keep it as an ACTION and call it from your own code.

---

## Tools Are Stubbable

Because a TOOL is just a schema plus a callable, swapping in a deterministic stub is trivial:

```python
stub_weather = TOOL(
    name="get_weather",
    description="Get the current weather for a city.",
    parameters={"city": {"type": "string"}},
    fn=lambda city: {"city": city, "temp": 0, "units": "celsius"},
)
```

Combined with [deterministic replay](replay.md) for the LLM side, an entire agent run becomes a fast, offline test.

---

## Design Philosophy

- **One line, drawn cleanly**: developer-invoked is ACTION; model-selected is TOOL
- **Schema is the interface**: the model reasons about the schema, not the code
- **Any callable works**: plain functions, lambdas, or promoted ACTIONs
- **Execution stays in the loop**: tools never touch memory; the agent records everything

For the complete API reference, see [primitives/TOOL.md](https://github.com/jrolf/thoughtflow/blob/main/primitives/TOOL.md).

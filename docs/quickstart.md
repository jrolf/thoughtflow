# Quick Start

Get up and running with ThoughtFlow in 5 minutes.

---

## Installation

```bash
pip install thoughtflow
```

The core library has **zero dependencies** -- it uses only Python's standard library.

---

## Your First THOUGHT

ThoughtFlow has one universal pattern: `memory = thought(memory)`. Here's a complete working example:

```python
import os
from thoughtflow import LLM, MEMORY, THOUGHT

api_key = os.environ.get("OPENAI_API_KEY")

llm = LLM("openai:gpt-4o", key=api_key)
memory = MEMORY()

memory.add_msg("user", "What is the meaning of life?")

thought = THOUGHT(
    name="respond",
    llm=llm,
    prompt="You are a wise philosopher. Answer: {last_user_msg}",
)

memory = thought(memory)

result = memory.get_var("respond_result")
print(result)
```

That's it. `THOUGHT` combines prompt + context + LLM call + parsing + validation into a single callable. `MEMORY` tracks everything that happens.

---

## Switching Providers

Changing providers is a one-line change. Your THOUGHT and MEMORY code stays the same:

```python
from thoughtflow import LLM

llm = LLM("openai:gpt-4o", key=openai_key)

llm = LLM("anthropic:claude-3-5-sonnet-20241022", key=anthropic_key)

llm = LLM("groq:llama-3.1-70b-versatile", key=groq_key)

llm = LLM("gemini:gemini-1.5-pro", key=gemini_key)

llm = LLM("ollama:llama3.2")  # Local models, no key needed
```

## Setting Default Parameters

You can set parameters once at construction time instead of repeating them on every call. Per-call values always override the defaults.

```python
llm = LLM(
    "openai:gpt-4o",
    key=openai_key,
    temperature=0.7,     # Controls randomness (0 = deterministic, 2 = creative)
    max_tokens=1024,     # Maximum response length
    top_p=0.95,          # Nucleus sampling threshold
    frequency_penalty=0.1,  # Reduces token repetition
    presence_penalty=0.0,   # Penalizes tokens that have appeared at all
)

# All calls use these defaults automatically
response = llm.call([{"role": "user", "content": "Hello"}])[0]

# Override just one; the others still apply
response = llm.call(messages, params={"temperature": 0.1})[0]
```

---

## Working with MEMORY

MEMORY is an event-sourced container. Every change is an event with a sortable ID:

```python
from thoughtflow import MEMORY

memory = MEMORY()

memory.add_msg("user", "Hello!")
memory.add_msg("assistant", "Hi there!")

memory.set_var("session_id", "abc123")
memory.set_var("request_count", 0)
memory.set_var("request_count", 1)
memory.set_var("request_count", 2)

memory.get_var("request_count")              # Returns: 2
memory.get_var_history("request_count")      # Returns every change with timestamps

memory.last_user_msg(content_only=True)      # "Hello!"

print(memory.render(format="conversation"))
```

---

## Chaining THOUGHTs

Build multi-step workflows by chaining thoughts together -- it's just a for loop:

```python
from thoughtflow import LLM, MEMORY, THOUGHT

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

analyze = THOUGHT(
    name="analyze",
    llm=llm,
    prompt="Identify the key themes in: {text}",
)

summarize = THOUGHT(
    name="summarize",
    llm=llm,
    prompt="Summarize these themes: {analyze_result}",
)

memory.set_var("text", "Your document here...")

for thought in [analyze, summarize]:
    memory = thought(memory)

print(memory.get_var("summarize_result"))
```

Each thought stores its result in `{name}_result`, so the next thought can reference it.

---

## Structured Output with Parsing

Extract structured data from messy LLM output:

```python
thought = THOUGHT(
    name="extract_info",
    llm=llm,
    prompt="Extract user information from: {text}",
    parsing_rules={
        "kind": "python",
        "format": {
            "name": "",
            "age": 0,
            "skills": [],
        }
    },
    max_retries=3,
)

memory.set_var("text", "My name is Alice, I'm 28, and I know Python and ML.")
memory = thought(memory)

info = memory.get_var("extract_info_result")
# {"name": "Alice", "age": 28, "skills": ["Python", "ML"]}
```

If parsing or validation fails, THOUGHT automatically retries with a repair prompt that explains what went wrong.

---

## Using Tools and Agents

Let the LLM decide which tools to call autonomously:

```python
from thoughtflow import LLM, MEMORY, TOOL, AGENT

llm = LLM("openai:gpt-4o", key="...")

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

AGENT runs the cycle: call LLM, parse tool requests, execute tools, feed results back, repeat -- until the LLM produces a final response.

---

## Saving and Loading State

MEMORY supports multiple serialization formats:

```python
memory.save("state.pkl")
memory.to_json("state.json")

restored = MEMORY()
restored.load("state.pkl")

restored = MEMORY.from_json("state.json")
```

---

## Next Steps

- [primitives/LLM.md](../primitives/LLM.md) -- Multi-provider model interface
- [primitives/MEMORY.md](../primitives/MEMORY.md) -- Event-sourced state container
- [primitives/THOUGHT.md](../primitives/THOUGHT.md) -- Atomic unit of cognition
- [primitives/ACTION.md](../primitives/ACTION.md) -- External operations
- [primitives/AGENT.md](../primitives/AGENT.md) -- Autonomous tool-use loop
- [README](../README.md) -- Full documentation with all primitives and patterns

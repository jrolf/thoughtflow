# Quick Start

Get up and running with ThoughtFlow in 5 minutes.

---

## Installation

```bash
# Core library (zero dependencies)
pip install thoughtflow

# With OpenAI support
pip install thoughtflow[openai]

# With Anthropic support
pip install thoughtflow[anthropic]

# With all providers
pip install thoughtflow[all-providers]
```

---

## Your First Agent

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

# 1. Create an adapter for your provider
adapter = OpenAIAdapter(api_key="your-api-key")
# Or use environment variable: export OPENAI_API_KEY=sk-...
# adapter = OpenAIAdapter()

# 2. Create an agent
agent = Agent(adapter)

# 3. Call with a message list
response = agent.call([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is ThoughtFlow?"}
])

print(response)
```

---

## Using Message Objects

You can use plain dicts or Message objects:

```python
from thoughtflow import Agent, Message
from thoughtflow.adapters import OpenAIAdapter

adapter = OpenAIAdapter()
agent = Agent(adapter)

# Using Message objects
response = agent.call([
    Message.system("You are helpful."),
    Message.user("Hello!"),
])
```

---

## Adding Tracing

Capture complete execution traces for debugging and evaluation:

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter
from thoughtflow.trace import Session

adapter = OpenAIAdapter()
agent = Agent(adapter)

# Create a session to capture the trace
session = Session()

response = agent.call(
    [{"role": "user", "content": "Hello!"}],
    session=session
)

# Inspect the trace
print(session.events)
print(f"Total tokens: {session.total_tokens}")

# Save for later analysis
session.save("trace.json")
```

---

## Switching Providers

ThoughtFlow makes it easy to switch between providers:

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter, AnthropicAdapter, LocalAdapter

# OpenAI
openai_agent = Agent(OpenAIAdapter())

# Anthropic
anthropic_agent = Agent(AnthropicAdapter())

# Local (Ollama)
local_agent = Agent(LocalAdapter(base_url="http://localhost:11434/v1"))

# Same interface for all!
messages = [{"role": "user", "content": "Hello!"}]
response = openai_agent.call(messages)
# response = anthropic_agent.call(messages)
# response = local_agent.call(messages)
```

---

## Next Steps

- [Agent Concepts](concepts/agent.md) - Deep dive into the Agent contract
- [Adapters](concepts/adapters.md) - Learn about provider adapters
- [Tracing](concepts/tracing.md) - Debug and evaluate your agents

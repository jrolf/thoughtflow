# Agent

The Agent is the fundamental primitive in ThoughtFlow—something that can be called with messages and parameters. Everything else is composition.

---

## The Agent Contract

```python
class Agent:
    def call(self, msg_list, params=None):
        """Call the agent with messages and optional parameters."""
        ...
```

That's it. Any object with a `call(msg_list, params)` method is an Agent.

---

## Basic Usage

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

adapter = OpenAIAdapter(api_key="...")
agent = Agent(adapter)

response = agent.call([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
])
```

---

## The AgentProtocol

ThoughtFlow defines a protocol that any agent-like object can satisfy:

```python
from thoughtflow.agent import AgentProtocol

class MyCustomAgent:
    def call(self, msg_list, params=None):
        return "Custom response"

agent = MyCustomAgent()
assert isinstance(agent, AgentProtocol)  # True!
```

---

## TracedAgent

Wrap any agent with tracing:

```python
from thoughtflow.agent import TracedAgent
from thoughtflow.trace import Session

session = Session()
traced = TracedAgent(agent, session)

response = traced.call(messages)

# Session now contains complete execution trace
print(session.events)
```

---

## Composition Patterns

### Retry Wrapper

```python
class RetryAgent:
    def __init__(self, agent, max_retries=3):
        self.agent = agent
        self.max_retries = max_retries

    def call(self, msg_list, params=None):
        for attempt in range(self.max_retries):
            try:
                return self.agent.call(msg_list, params)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
```

### Caching Wrapper

```python
class CachedAgent:
    def __init__(self, agent, cache):
        self.agent = agent
        self.cache = cache

    def call(self, msg_list, params=None):
        key = self._make_key(msg_list, params)
        if key in self.cache:
            return self.cache[key]
        response = self.agent.call(msg_list, params)
        self.cache[key] = response
        return response
```

---

## Design Philosophy

- **Explicit over implicit**: No hidden state or side effects
- **Composable**: Wrap agents to add behavior
- **Testable**: Easy to mock and verify
- **Portable**: Same interface across all providers

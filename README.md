# ThoughtFlow

[![PyPI version](https://badge.fury.io/py/thoughtflow.svg)](https://badge.fury.io/py/thoughtflow)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/jrolf/thoughtflow/actions/workflows/ci.yml/badge.svg)](https://github.com/jrolf/thoughtflow/actions/workflows/ci.yml)

**A minimal, explicit, Pythonic substrate for building reproducible, portable, testable LLM and agent systems.**

> *Tiny surface area. Explicit state. Portable execution. Deterministic testing.*

---

## Why ThoughtFlow?

The modern LLM/agent ecosystem often evolves into abstraction swamps—hidden state, magical callbacks, and frameworks that are hard to understand, test, and deploy.

**ThoughtFlow takes a different path:**

- ✅ **No hidden agent runtime** you can't reason about
- ✅ **No graph DSL** you must adopt to do anything serious
- ✅ **No implicit global memory** or callback chains
- ✅ **No abstraction layers** whose main job is wrapping other abstractions

Instead, ThoughtFlow makes orchestration logic **plain Python**: explicit inputs, explicit outputs, explicit state transitions, replayable sessions, deterministic evaluation paths.

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

## Quick Start

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

# Create an adapter for your provider
adapter = OpenAIAdapter(api_key="your-api-key")

# Create an agent
agent = Agent(adapter)

# Call with a message list (the universal currency)
response = agent.call([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is ThoughtFlow?"}
])

print(response)
```

---

## Core Concepts

### The Agent Contract

An Agent is something that can be called with messages and parameters:

```python
class Agent:
    def call(self, msg_list, params=None):
        raise NotImplementedError
```

That's it. Everything else is composition.

### Messages: Stable Schema, Minimal Assumptions

```python
msg_list = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Draft 3 names for a company."},
]
```

### Explicit Tracing

```python
from thoughtflow.trace import Session

session = Session()
response = agent.call(msg_list, session=session)

# Session captures everything: inputs, outputs, timing, tokens, costs
print(session.to_dict())
```

---

## Design Principles

1. **Tiny Surface Area**: Few powerful primitives over many specialized classes
2. **Explicit State**: All state is visible, serializable, and replayable
3. **Portability**: Works across OpenAI, Anthropic, local models, serverless
4. **Deterministic Testing**: Record/replay workflows, stable sessions, predictable behavior

---

## Project Status

🚧 **Alpha** - ThoughtFlow is under active development. The API may change.

See the [CHANGELOG](CHANGELOG.md) for version history.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) © James A. Rolfsen

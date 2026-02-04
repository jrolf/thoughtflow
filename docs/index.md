# ThoughtFlow

**A minimal, explicit, Pythonic substrate for building reproducible, portable, testable LLM and agent systems.**

---

## Why ThoughtFlow?

The modern LLM/agent ecosystem often evolves into abstraction swamps—hidden state, magical callbacks, and frameworks that are hard to understand, test, and deploy.

**ThoughtFlow takes a different path:**

- ✅ No hidden agent runtime you can't reason about
- ✅ No graph DSL you must adopt to do anything serious
- ✅ No implicit global memory or callback chains
- ✅ No abstraction layers whose main job is wrapping other abstractions

Instead, ThoughtFlow makes orchestration logic **plain Python**.

---

## Core Principles

### 1. Tiny Surface Area
Few powerful primitives over many specialized classes. Add new API only when it's truly a missing primitive.

### 2. Explicit State
All state is visible, serializable, and replayable. A run produces a structured trace of inputs, outputs, tool calls, timing, and costs.

### 3. Portability
Works across OpenAI, Anthropic, local models (Ollama), and serverless environments. Clean adapter boundaries.

### 4. Deterministic Testing
Record/replay workflows, stable sessions, predictable tool behaviors, no hidden non-determinism.

---

## Quick Start

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

# Create an adapter
adapter = OpenAIAdapter(api_key="your-api-key")

# Create an agent
agent = Agent(adapter)

# Call with messages
response = agent.call([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
])
```

See the [Quick Start Guide](quickstart.md) for more details.

---

## Installation

```bash
# Core only (zero dependencies)
pip install thoughtflow

# With provider support
pip install thoughtflow[openai]
pip install thoughtflow[anthropic]
pip install thoughtflow[all-providers]
```

---

## Project Status

🚧 **Alpha** - ThoughtFlow is under active development. APIs may change.

---

## License

[MIT](https://github.com/jrolf/thoughtflow/blob/main/LICENSE) © James A. Rolfsen

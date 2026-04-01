# ThoughtFlow

**Powerful AI systems from simple parts.**

A handful of composable primitives. Event-sourced memory. Autonomous agents. No framework overhead. Just Python.

---

## Why ThoughtFlow?

AI systems don't need to be complicated. The complexity lives in the problems you're solving, not in the tools you use to solve them.

- A few powerful primitives, not forty classes
- Every state change is visible and traceable
- Testing AI systems is as easy as testing regular code
- Zero dependencies -- core runs on stdlib only
- Serverless deployment is trivial, not heroic

---

## Core Primitives

| Primitive | What It Does | The Pattern |
|-----------|--------------|-------------|
| **LLM** | Unified interface to call any language model | `response = llm.call(messages)` |
| **MEMORY** | Event-sourced state container for everything | `memory.add_msg("user", "Hello!")` |
| **THOUGHT** | Atomic unit of cognition with retry/parsing | `memory = thought(memory)` |
| **ACTION** | External operations with consistent logging | `memory = action(memory, **kwargs)` |

---

## Quick Start

```python
from thoughtflow import LLM, MEMORY, THOUGHT

llm = LLM("openai:gpt-4o", key="your-api-key")
memory = MEMORY()
memory.add_msg("user", "What is the meaning of life?")

thought = THOUGHT(
    name="respond",
    llm=llm,
    prompt="You are a wise philosopher. Answer: {last_user_msg}",
)

memory = thought(memory)
print(memory.get_var("respond_result"))
```

The universal pattern is `memory = thought(memory)`. Everything flows through MEMORY.

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

🚧 **Alpha** -- ThoughtFlow is under active development. APIs may evolve based on feedback.

---

## License

[MIT](https://github.com/jrolf/thoughtflow/blob/main/LICENSE) © James A. Rolfsen

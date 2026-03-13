# CHAT

> The interactive loop for testing agents locally in a terminal or Jupyter notebook.

## Philosophy

Building an agent is one thing; testing it interactively is another. CHAT exists to wrap any ThoughtFlow-compatible callable (THOUGHT, ACTION, AGENT, or plain function) and provide a simple text-based conversation loop. You type, the agent responds, and the session continues until you exit. This is invaluable for development, debugging, and demos.

CHAT does not implement the agent logic. It provides the I/O layer: get user input, add it to memory, invoke the agent, extract the response, display it, repeat. The agent must follow the ThoughtFlow contract: `fn(memory) -> memory`. CHAT is designed to be subclassable: override `get_input()` and `display()` to swap the backend (e.g. web UI, Jupyter widget) while reusing all agent and memory interaction logic.

Within the ThoughtFlow ecosystem, CHAT is the human-in-the-loop wrapper. AGENT runs autonomously; CHAT adds a human at the keyboard. It is the right primitive when you want to iterate on agent behavior locally or run a conversational demo.

## How It Works

CHAT holds an `agent` (callable), a `memory` instance (fresh MEMORY if none provided), and configuration for greeting, exit commands, channel, and labels. Two modes: `run()` enters an interactive loop that repeatedly calls `get_input()`, checks for exit commands (`q` and `quit` are always active), invokes `turn(user_input)`, and displays the response via `display()`. `turn()` adds the user message to memory, invokes the agent, extracts the response (via custom `response_extractor` or by diffing event stamps to find new assistant messages), appends to `history`, and returns the response text.

Exceptions from the agent are caught and displayed as errors; the session does not crash. `on_start()` and `on_end()` hooks run at loop entry and exit (e.g. show greeting, show goodbye). Subclasses override `get_input()` and `display()` to change I/O (e.g. read from a socket, render HTML).

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `agent` | Callable with signature `fn(memory) -> memory`. THOUGHT, ACTION, AGENT, or plain function. |
| `memory` | Optional. Existing memory to continue a conversation. Default: fresh MEMORY(). |
| `greeting` | Optional. Message displayed when `run()` starts. |
| `exit_commands` | Optional. Additional exit words (case-insensitive). `q` and `quit` are always active. |
| `channel` | Channel tag for user messages. Default: `"cli"`. |
| `user_label` | Label before user input prompt. Default: `"You"`. |
| `agent_label` | Label before agent responses. Default: `"Agent"`. |
| `response_extractor` | Optional. Callable `fn(memory) -> str` to pull the agent's reply. When omitted, CHAT finds the new assistant message automatically. |

## Usage

```python
from thoughtflow import LLM, THOUGHT, CHAT, MEMORY

llm = LLM("openai:gpt-4o-mini", key="...")
responder = THOUGHT(
    name="respond",
    llm=llm,
    prompt="You are a helpful assistant. Respond to: {last_user_msg}",
)

chat = CHAT(responder, greeting="Hello! Type 'q' to quit.")
chat.run()  # Interactive loop
```

```python
# Programmatic / Jupyter cell-by-cell
chat = CHAT(responder)
response1 = chat.turn("What is ThoughtFlow?")
response2 = chat.turn("Tell me more.")
print(chat.history)   # [(user_text, agent_text), ...]
print(chat.memory)   # Full memory state
```

## Relationship to Other Primitives

- **THOUGHT / AGENT**: CHAT wraps any callable following the contract. It commonly wraps a THOUGHT (single-step) or AGENT (multi-step with tools).
- **MEMORY**: CHAT owns a memory instance. User messages are added with the configured channel; the agent reads from and writes to memory.
- **WORKFLOW**: A WORKFLOW can be wrapped by CHAT if it follows the contract, though typically CHAT wraps THOUGHT or AGENT for conversational flows.

## Considerations for Future Development

- Streaming support: display tokens as they arrive when the underlying agent/LLM supports it.
- Multi-turn context window management (e.g. truncate or summarize when memory grows large).
- Optional persistence: save/load chat history to resume sessions.
- Rich display hooks (e.g. markdown rendering, syntax highlighting) for `display()`.
- Support for multi-modal input (e.g. images) when `get_input()` is overridden.

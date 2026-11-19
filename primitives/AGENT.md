# AGENT

> The autonomous tool-use loop that makes an LLM into an agent.

## Philosophy

AGENT exists because an LLM alone cannot act. It can generate text, but it cannot search the web, run code, or query a database. The agentic loop bridges that gap: the LLM reasons about what to do, requests tool calls, and the framework executes them and feeds results back. This cycle continues until the LLM produces a final answer or a limit is reached.

AGENT is the base primitive for all agentic behavior in ThoughtFlow. It sits above LLM, TOOL, and MEMORY, orchestrating their interaction. The contract is simple: `memory = agent(memory)`. Whatever goes in comes out enriched with tool interactions and a final response. Subclasses (ReactAgent, ReflectAgent, PlanActAgent) override specific parts of the loop to implement different methodologies while inheriting the core execution and memory handling.

## How It Works

The core loop runs up to `max_iterations` times. Each iteration:

1. **Build messages** — System prompt plus conversation history from memory.
2. **Call the LLM** — With tool schemas in the params (OpenAI-compatible format).
3. **Parse tool calls** — The response may contain JSON with `tool_calls`, `tool_call`, or a single `name`/`arguments` structure.
4. **If no tool calls** — Treat the response as final. Store it in memory as assistant message and in `{name}_result`. Exit.
5. **If tool calls exist** — Run `on_tool_call` hook (if set). If it returns False, skip that call. Otherwise execute each tool, add "action" and "result" messages to memory, and repeat from step 1.

Tool interactions are stored in memory using "action" (the tool request) and "result" (the tool output) roles so the LLM sees the full context on the next iteration.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| llm | LLM instance for generation | Required |
| tools | List of TOOL instances | [] |
| system_prompt | System-level instructions | "You are a helpful assistant." |
| max_iterations | Max tool-use loop iterations | 10 |
| name | Identifier for logging and result storage | "agent" |
| on_tool_call | Callable(tool_name, arguments) called before each execution; return False to block | None |
| merge_augments | Fold augmenting memory events into user messages for LLM calls only | False |

## Native tool calls, governance, and resume

When the llm has `chat()` (`protocol="auto"` or `"native"`), AGENT uses native tool calls and follows a write-ahead contract: the assistant message with its `tool_calls` is written to MEMORY before any tool runs, a `checkpoint(memory)` hook fires after it and after every tool result, every `tool_call_id` is answered (including vetoed, unknown, and budget-skipped calls, which strict providers require), and pending work is derived from the transcript, so a crashed run continues without re-running answered calls. LLMs that only have `call()` keep the original text-JSON loop.

Governance options (native protocol only): `allow=[names]`; `policy={"refund": {"mode": "approve_over", "field": "amount", "limit": 100}}` with modes `allow`, `deny` (add `"halt": True` to end the run), `approve`, and `approve_over`, or a callable `policy(name, arguments)`; `budget={"max_model_calls", "max_tool_calls", "max_tokens"}`. A call that needs approval suspends the run (`memory.suspend`, `{name}_status == "suspended"`). Rehydrate the MEMORY later and call `agent(memory, decision={"approve": True})` (or a list or dict of call ids) to resume; repeating the decision never double-executes a tool.

`{name}_status` ends as `final`, `suspended`, `max_iterations`, `budget_exhausted`, `vetoed`, or `error`, and `{name}_outcome` carries counters (`model_calls`, `tool_calls`, token usage, `vetoed`). `tool_loop(memory, llm, tools, policy=..., budget=..., allow=..., checkpoint=..., decision=...)` is a one-call helper over the same code.

## Usage

```python
from thoughtflow import LLM, MEMORY, TOOL, AGENT

llm = LLM("openai:gpt-4o", key="sk-...")
tools = [TOOL("search", "Search the web", {"query": {"type": "string"}}, search_fn)]
agent = AGENT(llm=llm, tools=tools, system_prompt="You are helpful.")

memory = MEMORY()
memory.add_msg("user", "What is the weather in Paris?")
memory = agent(memory)
print(memory.get_var("agent_result"))
```

With an approval hook:

```python
def approve_tool(tool_name, arguments):
    return tool_name != "delete_file"

agent = AGENT(llm=llm, tools=tools, on_tool_call=approve_tool)
memory = agent(memory)
```

## Relationship to Other Primitives

- **LLM** — AGENT calls the LLM each iteration. The LLM never sees AGENT directly; it receives messages and params.
- **TOOL** — AGENT holds a list of TOOLs, converts them to schemas for the LLM, and executes them when the LLM requests.
- **MEMORY** — AGENT reads and writes memory. It builds messages from memory, adds tool interactions, and stores the final result.
- **ReactAgent, ReflectAgent, PlanActAgent** — Subclasses of AGENT. They override prompt building, response parsing, or add post-loop logic.

## Considerations for Future Development

- Streaming support for LLM responses during the loop.
- Structured output for tool-call parsing (reduce reliance on JSON-in-text).
- Configurable tool-call format adapters for non-OpenAI providers.
- Trace/event integration for each iteration and tool execution.
- Support for parallel tool execution when the LLM requests multiple calls at once.

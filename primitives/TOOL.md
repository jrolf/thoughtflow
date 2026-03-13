# TOOL

> LLM-selectable capability with a schema.

## Philosophy

TOOL exists because LLMs need a way to discover and invoke capabilities at runtime. The developer defines what is possible; the LLM decides what to do. This is the declarative counterpart to ACTION: ACTION is imperative (your code calls it), TOOL is declarative (the LLM selects it via a schema). The agent loop bridges the two worlds by executing the tool when the LLM requests it and feeding the result back.

The schema is the heart of TOOL. It gives the LLM a name, a description, and a parameter specification in JSON Schema format. That schema is formatted into the structure that OpenAI, Anthropic, and other providers expect for function calling. The LLM reasons over the schema, chooses when to call, and generates arguments. The framework runs the underlying function and returns the result. TOOL does not catch exceptions; it raises them so the agent loop can handle errors and retry or surface them appropriately.

## How It Works

TOOL wraps a callable with metadata: name, description, and parameters. Parameters are auto-normalized: flat dicts of property definitions (e.g., `{"query": {"type": "string"}}`) are wrapped into proper JSON Schema `{"type": "object", "properties": {...}}`. `to_schema()` returns the OpenAI function-calling format: `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}`.

When called with an arguments dict, TOOL unpacks it as keyword arguments and invokes the wrapped function. Execution is tracked: `execution_count`, `execution_history`, `last_result`, and `last_error` are updated on each call. Unlike ACTION, TOOL does not catch exceptions; it re-raises them for the agent loop to handle.

`from_action(action)` bridges ACTION to TOOL. It wraps the ACTION's function, passing `None` for the memory argument (ACTION fns expect `memory, **kwargs`; TOOL fns receive only `**kwargs` from the LLM). The agent loop is responsible for memory integration if needed. TOOL supports `to_dict()` and `from_dict()` for serialization; the function itself cannot be serialized, so a function registry is required for reconstruction.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| name | Unique identifier for the tool. Sent to the LLM as the function name. |
| description | Human-readable explanation of what the tool does. Helps the LLM decide when to use it. |
| parameters | JSON Schema dict. Can be a full `{"type": "object", "properties": {...}}` or a flat dict of property definitions (auto-wrapped). |
| fn | Callable to execute. Receives keyword arguments matching the parameter names. |

## Usage

```python
from thoughtflow import TOOL

def search_web(query, max_results=3):
    return {"results": ["result1", "result2"]}

tool = TOOL(
    name="web_search",
    description="Search the web for current information.",
    parameters={
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results"},
    },
    fn=search_web,
)

# Schema for LLM provider
schema = tool.to_schema()

# Execution (normally by agent loop)
result = tool({"query": "latest news"})
```

```python
# Promote an ACTION to a TOOL
from thoughtflow import ACTION, TOOL

search = ACTION(name="search", fn=search_fn)
tool = TOOL.from_action(
    search,
    description="Search the web",
    parameters={"query": {"type": "string"}},
)
```

## Relationship to Other Primitives

TOOL is the schema layer for LLM tool use. AGENT consumes TOOL instances, formats their schemas for the LLM, and executes them when the LLM requests a tool call. MCP returns TOOL instances; each MCP tool's `fn` calls back to the MCP server. ACTION is the imperative sibling: TOOL can wrap an ACTION via `from_action()`, but ACTION itself is never selected by the LLM. WORKFLOW and CHAT may pass tools to an AGENT or THOUGHT that supports tool calling.

## Considerations for Future Development

- Add adapter methods for provider-specific schema formats (Anthropic, Gemini) if they diverge from OpenAI.
- Consider structured error handling (e.g., tool-specific error types) for richer agent loop behavior.
- Evaluate whether `from_action()` should support passing memory at execution time for ACTIONs that need it.
- Document function registry patterns for `from_dict()` in multi-process or distributed settings.

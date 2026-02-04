# Tools

Tools are functions with contracts that agents can invoke. ThoughtFlow makes tool use explicit, testable, and auditable.

---

## The Tool Contract

```python
from thoughtflow.tools import Tool, ToolResult

class MyTool(Tool):
    name = "my_tool"
    description = "What this tool does"

    def get_schema(self):
        return {
            "type": "object",
            "properties": {...},
            "required": [...]
        }

    def call(self, payload, params=None):
        # Do something
        return ToolResult.ok(result)
```

---

## Basic Example

```python
from thoughtflow.tools import Tool, ToolResult

class Calculator(Tool):
    name = "calculator"
    description = "Perform arithmetic calculations"

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        }

    def call(self, payload, params=None):
        try:
            result = eval(payload["expression"])
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(str(e))
```

---

## ToolResult

Tools return `ToolResult` objects:

```python
# Success
return ToolResult.ok(output=42, duration_ms=15)

# Failure
return ToolResult.fail(error="Invalid input")

# With metadata
return ToolResult(
    success=True,
    output={"data": [1, 2, 3]},
    metadata={"source": "api", "cached": False}
)
```

---

## Tool Registry

Organize tools with a registry:

```python
from thoughtflow.tools import ToolRegistry

registry = ToolRegistry()

registry.register(calculator)
registry.register(web_search)
registry.register(file_reader)

# Get a tool
calc = registry.get("calculator")

# List all tools
all_tools = registry.list()

# Convert to provider format
openai_tools = registry.to_openai_tools()
anthropic_tools = registry.to_anthropic_tools()
```

---

## Provider Formats

Tools convert to provider-specific formats:

```python
# OpenAI format
tool.to_openai_tool()
# {
#     "type": "function",
#     "function": {
#         "name": "calculator",
#         "description": "...",
#         "parameters": {...}
#     }
# }

# Anthropic format
tool.to_anthropic_tool()
# {
#     "name": "calculator",
#     "description": "...",
#     "input_schema": {...}
# }
```

---

## Testing Tools

Tools are easy to test in isolation:

```python
def test_calculator():
    calc = Calculator()

    result = calc.call({"expression": "2 + 2"})
    assert result.success
    assert result.output == 4

    result = calc.call({"expression": "invalid"})
    assert not result.success
    assert result.error is not None
```

---

## Design Philosophy

- **Explicit invocation**: Tool calls are recorded steps
- **Traceable**: All tool calls captured in session
- **Testable**: Mock tools for deterministic tests
- **Provider-agnostic**: Same tool works with any adapter

#!/usr/bin/env python3
"""
ThoughtFlow Example 02: Tool Use with ACTION

Demonstrates how to define and use ACTIONs (tools) with ThoughtFlow.
ACTIONs wrap external operations with consistent logging and result storage.

Prerequisites:
    pip install thoughtflow

Run:
    python examples/02_tool_use.py
"""

from thoughtflow import MEMORY, ACTION
from thoughtflow.tools import Tool, ToolResult, ToolRegistry


# Define a simple calculator tool (using the Tool class)
class Calculator(Tool):
    """A calculator tool that evaluates mathematical expressions."""

    name = "calculator"
    description = "Evaluate a mathematical expression and return the result"

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '2 + 2' or '15 * 3'",
                }
            },
            "required": ["expression"],
        }

    def call(self, payload, params=None):
        expression = payload.get("expression", "")
        try:
            # WARNING: eval is dangerous in production! Use a safe math parser.
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolResult.ok(output=result)
        except Exception as e:
            return ToolResult.fail(error=f"Failed to evaluate: {e}")


# Define a weather tool (mock) as an ACTION
def get_weather(memory, location="Unknown"):
    """A mock weather function."""
    # Simulate weather API call
    return {
        "location": location,
        "temperature": 72,
        "condition": "sunny with light clouds",
        "unit": "F"
    }


def main():
    # Create a MEMORY instance
    memory = MEMORY()

    # --- Using Tool class directly ---
    print("--- Testing Calculator Tool ---")
    calculator = Calculator()
    result = calculator.call({"expression": "15 * 7 + 3"})
    print(f"Expression: 15 * 7 + 3")
    print(f"Result: {result.output}")
    print(f"Success: {result.success}")

    # --- Using ACTION wrapper ---
    print("\n--- Testing Weather ACTION ---")
    
    # Create an ACTION from a function
    weather_action = ACTION(
        name="weather",
        fn=get_weather,
        config={"location": "San Francisco, CA"},
        description="Get current weather for a location"
    )
    
    # Execute the action (logs to memory automatically)
    memory = weather_action(memory)
    
    # Get the result from memory
    weather_result = memory.get_var("weather_result")
    print(f"Location: {weather_result['location']}")
    print(f"Temperature: {weather_result['temperature']}°{weather_result['unit']}")
    print(f"Condition: {weather_result['condition']}")
    
    # Check execution stats
    print(f"\nExecution count: {weather_action.execution_count}")
    print(f"Successful: {weather_action.was_successful()}")

    # --- Tool Registry ---
    print("\n--- Tool Registry ---")
    registry = ToolRegistry()
    registry.register(calculator)

    print("Registered tools:")
    for name in registry.names():
        tool = registry.get(name)
        print(f"  - {name}: {tool.description}")

    # Show tool schemas in OpenAI format
    print("\n--- Tools in OpenAI Format ---")
    import json
    for tool_spec in registry.to_openai_tools():
        print(json.dumps(tool_spec, indent=2))

    # --- Show memory logs ---
    print("\n--- Memory Logs (ACTION execution tracking) ---")
    for log in memory.get_logs():
        print(f"  {log['content']}")


if __name__ == "__main__":
    main()

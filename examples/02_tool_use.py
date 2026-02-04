#!/usr/bin/env python3
"""
ThoughtFlow Example 02: Tool Use

Demonstrates how to define and use tools with ThoughtFlow.

Prerequisites:
    pip install thoughtflow[openai]
    export OPENAI_API_KEY=sk-...

Run:
    python examples/02_tool_use.py
"""

from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter
from thoughtflow.tools import Tool, ToolResult, ToolRegistry


# Define a simple calculator tool
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


# Define a weather tool (mock)
class Weather(Tool):
    """A mock weather tool."""

    name = "get_weather"
    description = "Get the current weather for a location"

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g., 'San Francisco, CA'",
                }
            },
            "required": ["location"],
        }

    def call(self, payload, params=None):
        location = payload.get("location", "Unknown")
        # Mock response
        return ToolResult.ok(
            output=f"Weather in {location}: 72°F, sunny with light clouds",
            cached=True,
        )


def main():
    # Create tools
    calculator = Calculator()
    weather = Weather()

    # Register tools
    registry = ToolRegistry()
    registry.register(calculator)
    registry.register(weather)

    print("Registered tools:")
    for name in registry.names():
        tool = registry.get(name)
        print(f"  - {name}: {tool.description}")

    # Test calculator directly
    print("\n--- Testing Calculator Tool ---")
    result = calculator.call({"expression": "15 * 7 + 3"})
    print(f"Expression: 15 * 7 + 3")
    print(f"Result: {result.output}")
    print(f"Success: {result.success}")

    # Test weather directly
    print("\n--- Testing Weather Tool ---")
    result = weather.call({"location": "San Francisco, CA"})
    print(f"Location: San Francisco, CA")
    print(f"Result: {result.output}")

    # Show tool schemas in OpenAI format
    print("\n--- Tools in OpenAI Format ---")
    import json

    for tool_spec in registry.to_openai_tools():
        print(json.dumps(tool_spec, indent=2))


if __name__ == "__main__":
    main()

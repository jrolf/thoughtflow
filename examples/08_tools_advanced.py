#!/usr/bin/env python3
"""
ThoughtFlow Example 08: Advanced Tools with Tool Class and ToolRegistry

Demonstrates the Tool class and ToolRegistry for building structured,
schema-defined tools that integrate with OpenAI and Anthropic function calling.

This is more advanced than ACTION:
- Tool: Abstract class for schema-defined tools with formal contracts
- ACTION: Simple wrapper for any function with logging

When to use which:
- Use ACTION for quick function wrapping with execution tracking
- Use Tool for OpenAI/Anthropic function calling with JSON schemas
- Tool provides to_openai_tool() and to_anthropic_tool() methods

Prerequisites:
    pip install thoughtflow

Run:
    python examples/08_tools_advanced.py
"""

import json
from thoughtflow.tools import Tool, ToolResult, ToolRegistry


# =============================================================================
# Custom Tool Implementations
# =============================================================================

class Calculator(Tool):
    """A calculator tool that evaluates mathematical expressions.
    
    This demonstrates a simple tool with input validation and
    proper error handling via ToolResult.
    """
    
    name = "calculator"
    description = "Evaluate a mathematical expression and return the numeric result"
    
    def get_schema(self):
        """Define the JSON Schema for the tool's input."""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate, e.g., '2 + 2' or 'sqrt(16)'"
                }
            },
            "required": ["expression"]
        }
    
    def call(self, payload, params=None):
        """Execute the calculation.
        
        Args:
            payload: Dict with 'expression' key
            params: Optional execution parameters (unused)
            
        Returns:
            ToolResult with the calculated value or error
        """
        expression = payload.get("expression", "")
        
        if not expression:
            return ToolResult.fail("No expression provided")
        
        try:
            # WARNING: eval is dangerous in production!
            # Use a safe math parser like 'numexpr' or 'asteval'
            import math
            safe_dict = {
                "__builtins__": {},
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "pi": math.pi,
                "e": math.e,
                "abs": abs,
                "round": round,
            }
            result = eval(expression, safe_dict, {})
            return ToolResult.ok(output=result, expression=expression)
        except Exception as e:
            return ToolResult.fail(f"Calculation error: {e}")


class WebSearch(Tool):
    """A web search tool (mock implementation).
    
    Demonstrates a tool with multiple parameters and metadata.
    """
    
    name = "web_search"
    description = "Search the web for information on a topic"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5
                },
                "site": {
                    "type": "string",
                    "description": "Optional: limit search to specific site"
                }
            },
            "required": ["query"]
        }
    
    def call(self, payload, params=None):
        query = payload.get("query", "")
        max_results = payload.get("max_results", 5)
        site = payload.get("site")
        
        if not query:
            return ToolResult.fail("No query provided")
        
        # Mock search results
        results = [
            {"title": f"Result 1 for '{query}'", "url": "https://example.com/1", "snippet": "..."},
            {"title": f"Result 2 for '{query}'", "url": "https://example.com/2", "snippet": "..."},
            {"title": f"Result 3 for '{query}'", "url": "https://example.com/3", "snippet": "..."},
        ][:max_results]
        
        return ToolResult.ok(
            output=results,
            query=query,
            site=site,
            result_count=len(results)
        )


class SendEmail(Tool):
    """An email sending tool (mock implementation).
    
    Demonstrates a tool with complex input schema.
    """
    
    name = "send_email"
    description = "Send an email to one or more recipients"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email addresses"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body content"
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipients"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Email priority level"
                }
            },
            "required": ["to", "subject", "body"]
        }
    
    def call(self, payload, params=None):
        to = payload.get("to", [])
        subject = payload.get("subject", "")
        body = payload.get("body", "")
        
        if not to:
            return ToolResult.fail("No recipients provided")
        if not subject:
            return ToolResult.fail("No subject provided")
        
        # Mock sending (in real implementation, use smtplib, etc.)
        message_id = f"msg_{hash(subject) % 100000:05d}"
        
        return ToolResult.ok(
            output={"message_id": message_id, "status": "sent"},
            recipients=to,
            subject=subject
        )


class DatabaseQuery(Tool):
    """A database query tool (mock implementation).
    
    Demonstrates a tool that could be dangerous without proper validation.
    """
    
    name = "database_query"
    description = "Execute a read-only SQL query against the database"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100
                }
            },
            "required": ["query"]
        }
    
    def call(self, payload, params=None):
        query = payload.get("query", "")
        limit = payload.get("limit", 100)
        
        # Safety check: only allow SELECT
        if not query.strip().upper().startswith("SELECT"):
            return ToolResult.fail("Only SELECT queries are allowed")
        
        # Mock database result
        mock_data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ][:limit]
        
        return ToolResult.ok(
            output=mock_data,
            row_count=len(mock_data),
            query=query[:50] + "..." if len(query) > 50 else query
        )


# =============================================================================
# Main Demo
# =============================================================================

def main():
    print("--- ThoughtFlow Advanced Tools Demo ---\n")
    
    # =========================================================================
    # Part 1: Creating and Using Individual Tools
    # =========================================================================
    print("=== Part 1: Using Individual Tools ===\n")
    
    # Create tool instances
    calculator = Calculator()
    web_search = WebSearch()
    
    # Use the calculator
    result = calculator.call({"expression": "sqrt(16) + 2 * 3"})
    print(f"Calculator: sqrt(16) + 2 * 3 = {result.output}")
    print(f"  Success: {result.success}")
    print(f"  Metadata: {result.metadata}")
    
    # Use web search
    result = web_search.call({"query": "ThoughtFlow Python", "max_results": 2})
    print(f"\nWeb Search: Found {result.metadata['result_count']} results")
    for r in result.output:
        print(f"  - {r['title']}")
    
    # =========================================================================
    # Part 2: Tool Schemas
    # =========================================================================
    print("\n=== Part 2: Tool Schemas ===\n")
    
    print("Calculator schema:")
    print(json.dumps(calculator.get_schema(), indent=2))
    
    print("\nSend Email schema (complex):")
    send_email = SendEmail()
    print(json.dumps(send_email.get_schema(), indent=2))
    
    # =========================================================================
    # Part 3: ToolRegistry for Managing Multiple Tools
    # =========================================================================
    print("\n=== Part 3: ToolRegistry ===\n")
    
    # Create a registry and register tools
    registry = ToolRegistry()
    registry.register(Calculator())
    registry.register(WebSearch())
    registry.register(SendEmail())
    registry.register(DatabaseQuery())
    
    print(f"Registered {len(registry)} tools:")
    for name in registry.names():
        tool = registry.get(name)
        print(f"  - {name}: {tool.description[:50]}...")
    
    # Check if tool exists
    print(f"\n'calculator' in registry: {'calculator' in registry}")
    print(f"'unknown' in registry: {'unknown' in registry}")
    
    # Get and use a tool from registry
    calc = registry.get("calculator")
    result = calc.call({"expression": "pi * 2"})
    print(f"\nUsing registry tool: pi * 2 = {result.output:.4f}")
    
    # =========================================================================
    # Part 4: OpenAI Function Calling Format
    # =========================================================================
    print("\n=== Part 4: OpenAI Function Calling Format ===\n")
    
    # Convert single tool
    openai_spec = calculator.to_openai_tool()
    print("Single tool in OpenAI format:")
    print(json.dumps(openai_spec, indent=2))
    
    # Convert all registry tools
    print("\nAll tools in OpenAI format (for API call):")
    openai_tools = registry.to_openai_tools()
    for tool_spec in openai_tools:
        print(f"  - {tool_spec['function']['name']}")
    
    print(f"\nTotal: {len(openai_tools)} tools ready for OpenAI API")
    
    # =========================================================================
    # Part 5: Anthropic Function Calling Format
    # =========================================================================
    print("\n=== Part 5: Anthropic Function Calling Format ===\n")
    
    anthropic_spec = calculator.to_anthropic_tool()
    print("Single tool in Anthropic format:")
    print(json.dumps(anthropic_spec, indent=2))
    
    print("\nAll tools in Anthropic format:")
    anthropic_tools = registry.to_anthropic_tools()
    for tool_spec in anthropic_tools:
        print(f"  - {tool_spec['name']}")
    
    # =========================================================================
    # Part 6: Error Handling with ToolResult
    # =========================================================================
    print("\n=== Part 6: Error Handling ===\n")
    
    # Successful result
    result = ToolResult.ok(output=42, computation="6 * 7")
    print(f"Success result: {result.output}, metadata: {result.metadata}")
    
    # Failed result
    result = ToolResult.fail("Division by zero", expression="1/0")
    print(f"Failure result: error='{result.error}', metadata: {result.metadata}")
    
    # Handle tool errors gracefully
    db_tool = registry.get("database_query")
    result = db_tool.call({"query": "DROP TABLE users"})  # Should fail
    if not result.success:
        print(f"\nSafety check caught bad query: {result.error}")
    
    # =========================================================================
    # Part 7: Tool vs ACTION Comparison
    # =========================================================================
    print("\n=== Part 7: Tool vs ACTION ===\n")
    
    print("""
    ┌─────────────────┬───────────────────────────────────────────────────┐
    │ Feature         │ Tool                    │ ACTION                  │
    ├─────────────────┼─────────────────────────┼─────────────────────────┤
    │ Definition      │ Class with schema       │ Wraps any function      │
    │ Input Schema    │ JSON Schema (required)  │ Not required            │
    │ Output          │ ToolResult dataclass    │ Any value               │
    │ Error handling  │ ToolResult.fail()       │ Caught, logged          │
    │ OpenAI format   │ to_openai_tool()        │ Not supported           │
    │ Anthropic format│ to_anthropic_tool()     │ Not supported           │
    │ Memory logging  │ Manual                  │ Automatic               │
    │ Execution track │ Manual                  │ Built-in history        │
    │ Registry        │ ToolRegistry            │ Use dict or list        │
    └─────────────────┴─────────────────────────┴─────────────────────────┘
    
    Use Tool when:
    - You need OpenAI/Anthropic function calling
    - You want formal JSON Schema input validation
    - Building reusable, documented tool libraries
    
    Use ACTION when:
    - Quick function wrapping with logging
    - Don't need API function calling format
    - Want automatic execution history tracking
    """)
    
    # =========================================================================
    # Part 8: Integrating Tools with LLM Function Calling (Pattern)
    # =========================================================================
    print("=== Part 8: LLM Function Calling Pattern ===\n")
    
    print("""
    Example pattern for OpenAI function calling:
    
    ```python
    from thoughtflow import LLM
    from thoughtflow.tools import ToolRegistry
    
    # Setup
    llm = LLM("openai:gpt-4o", key="...")
    registry = ToolRegistry()
    registry.register(Calculator())
    registry.register(WebSearch())
    
    # Make LLM call with tools
    messages = [{"role": "user", "content": "What is 15 * 7?"}]
    
    response = llm.call(
        messages,
        tools=registry.to_openai_tools(),
        tool_choice="auto"
    )
    
    # If LLM wants to call a tool
    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool = registry.get(tool_call.function.name)
            args = json.loads(tool_call.function.arguments)
            result = tool.call(args)
            # Add result to messages and continue conversation
    ```
    """)
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("=== Summary ===\n")
    print("""
    Tool system components:
    
    1. Tool (abstract class):
       - Subclass and implement call() and get_schema()
       - Provides to_openai_tool() and to_anthropic_tool()
    
    2. ToolResult (dataclass):
       - ToolResult.ok(output, **metadata) for success
       - ToolResult.fail(error, **metadata) for failure
       - Consistent result structure
    
    3. ToolRegistry:
       - register(tool) / unregister(name)
       - get(name) / list() / names()
       - to_openai_tools() / to_anthropic_tools()
    
    Key benefits:
    - Schema-defined inputs with JSON Schema
    - Compatible with OpenAI and Anthropic function calling
    - Structured error handling
    - Centralized tool management
    """)


if __name__ == "__main__":
    main()

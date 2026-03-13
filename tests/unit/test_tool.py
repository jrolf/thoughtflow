"""
Unit tests for the ThoughtFlow TOOL class.

The TOOL class wraps a callable and adds an LLM-visible schema (name,
description, parameters) for function-calling / tool-use. Key boundary:
- ACTION is imperative (your code calls it)
- TOOL is declarative (the LLM selects it via schema)

Tests cover: initialization, schema generation, execution, from_action
bridge, serialization, and error handling.
"""

from __future__ import annotations

import pytest

from thoughtflow.tool import TOOL
from thoughtflow import ACTION


# ============================================================================
# Initialization Tests
# ============================================================================


class TestToolInitialization:
    """Tests for TOOL class initialization."""

    def test_stores_name_and_description(self):
        """
        TOOL must store the provided name and description.

        These are sent to the LLM so it can decide when to call the tool.

        Remove this test if: We change the initialization signature.
        """
        tool = TOOL(
            name="calculator",
            description="Perform arithmetic",
            parameters={"type": "object", "properties": {}},
            fn=lambda: None,
        )

        assert tool.name == "calculator"
        assert tool.description == "Perform arithmetic"

    def test_generates_unique_id(self):
        """
        Each TOOL must have a unique ID.

        Remove this test if: We change ID generation.
        """
        tool1 = TOOL("t1", "d1", {}, lambda: None)
        tool2 = TOOL("t2", "d2", {}, lambda: None)

        assert tool1.id != tool2.id

    def test_stores_function_reference(self):
        """
        TOOL must store the function for later execution.

        Remove this test if: We change how functions are stored.
        """
        def my_func(x):
            return x * 2

        tool = TOOL("test", "desc", {}, my_func)

        assert tool.fn is my_func

    def test_normalizes_flat_parameters(self):
        """
        TOOL must wrap a flat dict of property definitions into proper JSON Schema.

        This makes the constructor ergonomic for simple cases where the user
        just passes property definitions without the "type"/"properties" wrapper.

        Remove this test if: We change parameter normalization.
        """
        tool = TOOL(
            name="search",
            description="Search",
            parameters={
                "query": {"type": "string", "description": "Search query"},
            },
            fn=lambda query: query,
        )

        assert tool.parameters["type"] == "object"
        assert "query" in tool.parameters["properties"]

    def test_passes_through_proper_schema(self):
        """
        TOOL must pass through already-structured JSON Schema unchanged.

        Remove this test if: We change parameter normalization.
        """
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        }
        tool = TOOL("search", "Search", schema, lambda query: query)

        assert tool.parameters == schema

    def test_empty_parameters(self):
        """
        TOOL must handle empty/None parameters gracefully.

        Remove this test if: We change parameter handling.
        """
        tool = TOOL("noop", "Does nothing", {}, lambda: None)

        assert tool.parameters["type"] == "object"
        assert tool.parameters["properties"] == {}

    def test_initial_execution_state(self):
        """
        TOOL must start with zero executions and no results.

        Remove this test if: We change execution tracking.
        """
        tool = TOOL("test", "desc", {}, lambda: None)

        assert tool.execution_count == 0
        assert tool.last_result is None
        assert tool.last_error is None
        assert tool.execution_history == []


# ============================================================================
# Schema Generation Tests
# ============================================================================


class TestToolSchema:
    """Tests for TOOL.to_schema() method."""

    def test_generates_openai_format(self):
        """
        to_schema() must return OpenAI function-calling format.

        This is the canonical format used across the framework.

        Remove this test if: We change the canonical schema format.
        """
        tool = TOOL(
            name="get_weather",
            description="Get current weather for a city.",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
            fn=lambda city: {"temp": 72},
        )

        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_weather"
        assert schema["function"]["description"] == "Get current weather for a city."
        assert "city" in schema["function"]["parameters"]["properties"]

    def test_schema_includes_required_fields(self):
        """
        to_schema() must preserve the 'required' field from parameters.

        Remove this test if: We change schema generation.
        """
        tool = TOOL(
            name="search",
            description="Search",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            fn=lambda query: query,
        )

        schema = tool.to_schema()
        assert schema["function"]["parameters"]["required"] == ["query"]


# ============================================================================
# Execution Tests
# ============================================================================


class TestToolExecution:
    """Tests for TOOL execution behavior."""

    def test_executes_function_with_arguments(self):
        """
        TOOL must execute the wrapped function with the provided arguments.

        Remove this test if: We change the execution signature.
        """
        def add(a, b):
            return a + b

        tool = TOOL("add", "Add two numbers", {}, add)
        result = tool({"a": 2, "b": 3})

        assert result == 5

    def test_executes_with_no_arguments(self):
        """
        TOOL must handle execution with no arguments.

        Remove this test if: We change argument handling.
        """
        tool = TOOL("time", "Get current time", {}, lambda: "12:00")
        result = tool()

        assert result == "12:00"

    def test_tracks_execution_count(self):
        """
        TOOL must track how many times it has been executed.

        Remove this test if: We remove execution tracking.
        """
        tool = TOOL("counter", "Count", {}, lambda: "ok")

        tool()
        tool()
        tool()

        assert tool.execution_count == 3

    def test_stores_last_result(self):
        """
        TOOL must record the most recent result.

        Remove this test if: We remove result recording.
        """
        tool = TOOL("doubler", "Double", {}, lambda x: x * 2)

        tool({"x": 5})

        assert tool.last_result == 10

    def test_tracks_execution_history(self):
        """
        TOOL must record execution history with timing.

        Remove this test if: We change history format.
        """
        tool = TOOL("test", "Test", {}, lambda: "ok")
        tool()

        assert len(tool.execution_history) == 1
        entry = tool.execution_history[0]
        assert entry['success'] is True
        assert 'duration_ms' in entry

    def test_raises_on_function_error(self):
        """
        TOOL must propagate exceptions from the wrapped function.

        Unlike ACTION (which catches exceptions), TOOL raises them so
        the agent loop can decide how to handle the error.

        Remove this test if: We change error handling policy.
        """
        def failing_fn():
            raise ValueError("Something broke")

        tool = TOOL("failing", "Fails", {}, failing_fn)

        with pytest.raises(ValueError, match="Something broke"):
            tool()

    def test_records_error_in_history(self):
        """
        TOOL must record failed executions in history.

        Remove this test if: We remove history tracking.
        """
        def failing_fn():
            raise RuntimeError("Oops")

        tool = TOOL("failing", "Fails", {}, failing_fn)

        with pytest.raises(RuntimeError):
            tool()

        assert tool.execution_count == 1
        assert tool.last_error is not None
        assert tool.execution_history[-1]['success'] is False


# ============================================================================
# From ACTION Bridge Tests
# ============================================================================


class TestToolFromAction:
    """Tests for TOOL.from_action() class method."""

    def test_creates_tool_from_action(self):
        """
        from_action() must create a TOOL wrapping an ACTION's function.

        Remove this test if: We change the ACTION-to-TOOL bridge.
        """
        action = ACTION(
            name="search",
            fn=lambda mem, query="": {"hits": [query]},
            description="Search the web",
        )
        tool = TOOL.from_action(
            action,
            parameters={"query": {"type": "string"}},
        )

        assert tool.name == "search"
        assert "Search the web" in tool.description

    def test_from_action_inherits_name(self):
        """
        from_action() must use the ACTION's name.

        Remove this test if: We change name inheritance.
        """
        action = ACTION(name="fetch_data", fn=lambda mem: None)
        tool = TOOL.from_action(action, parameters={})

        assert tool.name == "fetch_data"

    def test_from_action_override_description(self):
        """
        from_action() must allow overriding the description.

        Remove this test if: We remove description override.
        """
        action = ACTION(name="test", fn=lambda mem: None, description="Old desc")
        tool = TOOL.from_action(action, description="New desc", parameters={})

        assert tool.description == "New desc"

    def test_from_action_tool_is_callable(self):
        """
        A TOOL created from an ACTION must be callable with keyword args.

        The wrapper skips the leading 'mem' argument that ACTION fns expect,
        so the TOOL receives only the keyword arguments from the LLM.

        Remove this test if: We change the from_action execution model.
        """
        # ACTION fns have signature (memory, **kwargs), but when promoted to
        # a TOOL the wrapper strips the memory argument. To test this, we
        # define a function whose real work is in the kwargs.
        def raw_fn(mem, x=0, y=0):
            return x + y

        action = ACTION(name="add", fn=raw_fn)
        tool = TOOL.from_action(
            action,
            parameters={
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
        )

        # TOOL calls should NOT pass memory — just keyword args
        result = tool({"x": 3, "y": 4})
        assert result == 7

    def test_from_action_generates_valid_schema(self):
        """
        A TOOL from an ACTION must produce a valid schema.

        Remove this test if: We change schema generation.
        """
        action = ACTION(name="lookup", fn=lambda mem, term="": term)
        tool = TOOL.from_action(
            action,
            description="Look up a term",
            parameters={"term": {"type": "string", "description": "The term"}},
        )

        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "lookup"
        assert "term" in schema["function"]["parameters"]["properties"]


# ============================================================================
# Serialization Tests
# ============================================================================


class TestToolSerialization:
    """Tests for TOOL serialization and deserialization."""

    def test_to_dict_captures_config(self):
        """
        to_dict() must capture tool configuration.

        Remove this test if: We remove serialization.
        """
        tool = TOOL(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            fn=lambda x: x,
        )

        data = tool.to_dict()

        assert data['name'] == 'test_tool'
        assert data['description'] == 'A test tool'
        assert 'x' in data['parameters']['properties']

    def test_from_dict_restores_tool(self):
        """
        from_dict() must restore a TOOL from a dict using a function registry.

        Remove this test if: We change deserialization.
        """
        def my_func(x):
            return x * 2

        original = TOOL("doubler", "Double a number", {}, my_func)
        data = original.to_dict()

        fn_registry = {"my_func": my_func}
        restored = TOOL.from_dict(data, fn_registry)

        assert restored.name == "doubler"
        assert restored.description == "Double a number"
        assert restored({"x": 5}) == 10

    def test_from_dict_raises_on_missing_function(self):
        """
        from_dict() must raise KeyError if the function is not in the registry.

        Remove this test if: We change deserialization error handling.
        """
        data = {"name": "test", "description": "test", "parameters": {},
                "fn_name": "missing_fn", "id": "123"}

        with pytest.raises(KeyError, match="missing_fn"):
            TOOL.from_dict(data, {})


# ============================================================================
# String Representation Tests
# ============================================================================


class TestToolRepr:
    """Tests for TOOL string representations."""

    def test_str(self):
        """TOOL __str__ must show name and execution count."""
        tool = TOOL("search", "Search", {}, lambda: None)
        assert "search" in str(tool)
        assert "0" in str(tool)

    def test_repr(self):
        """TOOL __repr__ must show name and description."""
        tool = TOOL("search", "Search the web", {}, lambda: None)
        assert "search" in repr(tool)
        assert "Search the web" in repr(tool)

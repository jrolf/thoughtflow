"""
Unit tests for the ThoughtFlow AGENT class and its subclasses
(ReactAgent, ReflectAgent, PlanActAgent).

Tests use the MockLLM from conftest to simulate LLM responses without HTTP calls.
"""

from __future__ import annotations

import json

import pytest

from thoughtflow.agent import AGENT
from thoughtflow.agents.react import ReactAgent
from thoughtflow.agents.reflect import ReflectAgent
from thoughtflow.agents.planact import PlanActAgent
from thoughtflow.tool import TOOL
from thoughtflow import MEMORY


# ============================================================================
# Helpers
# ============================================================================


def make_add_tool():
    """Create a simple addition TOOL for testing."""
    return TOOL(
        name="add",
        description="Add two numbers together.",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
        fn=lambda a, b: a + b,
    )


def make_echo_tool():
    """Create a simple echo TOOL for testing."""
    return TOOL(
        name="echo",
        description="Echo back the input text.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
        },
        fn=lambda text="": "Echo: {}".format(text),
    )


class MockLLM:
    """Mock LLM that returns configurable responses in sequence."""

    def __init__(self, responses=None):
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.calls = []
        self.service = "mock"
        self.model = "mock-model"

    def call(self, msgs, params=None):
        self.calls.append({'msgs': msgs, 'params': params or {}})
        idx = self.call_count % len(self.responses)
        response = self.responses[idx]
        self.call_count += 1
        return [response]


# ============================================================================
# Base AGENT Tests
# ============================================================================


class TestAgentInitialization:
    """Tests for AGENT initialization."""

    def test_stores_configuration(self):
        """AGENT must store all configuration attributes."""
        llm = MockLLM()
        tools = [make_add_tool()]

        agent = AGENT(llm=llm, tools=tools, system_prompt="Be helpful.", name="test")

        assert agent.name == "test"
        assert agent.llm is llm
        assert len(agent.tools) == 1
        assert agent.system_prompt == "Be helpful."
        assert agent.max_iterations == 10

    def test_generates_unique_id(self):
        """Each AGENT must have a unique ID."""
        a1 = AGENT(llm=MockLLM(), name="a1")
        a2 = AGENT(llm=MockLLM(), name="a2")
        assert a1.id != a2.id

    def test_builds_tool_map(self):
        """AGENT must build a name->tool lookup map."""
        tools = [make_add_tool(), make_echo_tool()]
        agent = AGENT(llm=MockLLM(), tools=tools)

        assert "add" in agent._tool_map
        assert "echo" in agent._tool_map


class TestAgentExecution:
    """Tests for AGENT execution behavior."""

    def test_returns_memory(self):
        """
        AGENT must return the memory instance (contract: memory = agent(memory)).
        """
        llm = MockLLM(responses=["Hello!"])
        agent = AGENT(llm=llm, name="test")
        memory = MEMORY()
        memory.add_msg("user", "Hi")

        result = agent(memory)

        assert result is memory

    def test_final_response_stored_in_memory(self):
        """
        AGENT must store the final text response in memory when no tool calls.
        """
        llm = MockLLM(responses=["The answer is 42."])
        agent = AGENT(llm=llm, name="test")
        memory = MEMORY()
        memory.add_msg("user", "What is the answer?")

        memory = agent(memory)

        assert memory.get_var("test_result") == "The answer is 42."

    def test_tool_call_and_response_cycle(self):
        """
        AGENT must execute tools when the LLM requests them, then get a final response.
        """
        # First response: tool call. Second response: final answer.
        tool_call_json = json.dumps({"name": "add", "arguments": {"a": 5, "b": 3}})
        llm = MockLLM(responses=[tool_call_json, "The sum is 8."])

        agent = AGENT(llm=llm, tools=[make_add_tool()], name="calc")
        memory = MEMORY()
        memory.add_msg("user", "Add 5 and 3")

        memory = agent(memory)

        assert memory.get_var("calc_result") == "The sum is 8."
        assert llm.call_count == 2

    def test_max_iterations_prevents_infinite_loop(self):
        """
        AGENT must stop after max_iterations even if the LLM keeps requesting tools.
        """
        tool_call_json = json.dumps({"name": "echo", "arguments": {"text": "loop"}})
        llm = MockLLM(responses=[tool_call_json])

        agent = AGENT(llm=llm, tools=[make_echo_tool()], max_iterations=3, name="loop")
        memory = MEMORY()
        memory.add_msg("user", "Keep going")

        memory = agent(memory)

        assert agent.iteration_count == 3

    def test_on_tool_call_hook_can_block(self):
        """
        AGENT must respect on_tool_call returning False to block execution.
        """
        blocked_tools = []

        def blocker(name, args):
            blocked_tools.append(name)
            return False

        tool_call_json = json.dumps({"name": "add", "arguments": {"a": 1, "b": 2}})
        llm = MockLLM(responses=[tool_call_json, "Blocked."])

        agent = AGENT(llm=llm, tools=[make_add_tool()], on_tool_call=blocker)
        memory = MEMORY()
        memory.add_msg("user", "Add numbers")
        memory = agent(memory)

        assert "add" in blocked_tools

    def test_missing_tool_returns_error(self):
        """
        AGENT must handle requests for non-existent tools gracefully.
        """
        tool_call_json = json.dumps({"name": "nonexistent", "arguments": {}})
        llm = MockLLM(responses=[tool_call_json, "Tool not found, sorry."])

        agent = AGENT(llm=llm, tools=[], name="test")
        memory = MEMORY()
        memory.add_msg("user", "Do something")
        memory = agent(memory)

        assert memory.get_var("test_result") == "Tool not found, sorry."


# ============================================================================
# ReactAgent Tests
# ============================================================================


class TestReactAgent:
    """Tests for the ReactAgent subclass."""

    def test_react_parses_final_answer(self):
        """
        ReactAgent must extract the Final Answer from ReAct-formatted output.
        """
        react_response = (
            "Thought: I know the answer.\n"
            "Final Answer: The capital of France is Paris."
        )
        llm = MockLLM(responses=[react_response])

        agent = ReactAgent(llm=llm, name="react_test")
        memory = MEMORY()
        memory.add_msg("user", "What is the capital of France?")
        memory = agent(memory)

        assert memory.get_var("react_test_result") == "The capital of France is Paris."

    def test_react_parses_tool_call(self):
        """
        ReactAgent must parse Action/Action Input lines into tool calls.
        """
        react_step = (
            "Thought: I need to search for this.\n"
            "Action: echo\n"
            'Action Input: {"text": "hello"}'
        )
        final = "Thought: Got it.\nFinal Answer: Echo says hello."
        llm = MockLLM(responses=[react_step, final])

        agent = ReactAgent(llm=llm, tools=[make_echo_tool()], name="react_test")
        memory = MEMORY()
        memory.add_msg("user", "Echo hello")
        memory = agent(memory)

        assert "hello" in memory.get_var("react_test_result").lower()

    def test_react_includes_tool_descriptions_in_prompt(self):
        """
        ReactAgent must inject tool descriptions into the system prompt.
        """
        llm = MockLLM(responses=["Final Answer: Done."])
        agent = ReactAgent(llm=llm, tools=[make_echo_tool()], name="test")
        memory = MEMORY()
        memory.add_msg("user", "Test")
        agent(memory)

        system_msg = llm.calls[0]['msgs'][0]['content']
        assert "echo" in system_msg.lower()


# ============================================================================
# ReflectAgent Tests
# ============================================================================


class TestReflectAgent:
    """Tests for the ReflectAgent subclass."""

    def test_reflect_approves_good_response(self):
        """
        ReflectAgent must skip revision when critique says APPROVED.
        """
        llm = MockLLM(responses=[
            "Here is my answer.",  # initial response
            "APPROVED",            # critique
        ])

        agent = ReflectAgent(llm=llm, name="reflect_test", max_revisions=2)
        memory = MEMORY()
        memory.add_msg("user", "Write something.")
        memory = agent(memory)

        assert memory.get_var("reflect_test_result") == "Here is my answer."
        assert len(agent.revision_history) == 1

    def test_reflect_revises_when_critique_fails(self):
        """
        ReflectAgent must revise when the critique identifies issues.
        """
        llm = MockLLM(responses=[
            "Draft answer.",                    # initial response
            "The response lacks detail.",       # critique (not approved)
            "Improved detailed answer.",        # revision
            "APPROVED",                         # second critique
        ])

        agent = ReflectAgent(llm=llm, name="reflect_test", max_revisions=2)
        memory = MEMORY()
        memory.add_msg("user", "Write something.")
        memory = agent(memory)

        assert memory.get_var("reflect_test_result") == "Improved detailed answer."
        assert len(agent.revision_history) == 2

    def test_reflect_respects_max_revisions(self):
        """
        ReflectAgent must stop after max_revisions even if not approved.
        """
        llm = MockLLM(responses=[
            "Draft.",             # initial
            "Needs work.",        # critique 1
            "Better draft.",      # revision 1
            "Still needs work.",  # critique 2 (max reached)
        ])

        agent = ReflectAgent(llm=llm, name="test", max_revisions=2)
        memory = MEMORY()
        memory.add_msg("user", "Write.")
        memory = agent(memory)

        assert len(agent.revision_history) <= 2


# ============================================================================
# PlanActAgent Tests
# ============================================================================


class TestPlanActAgent:
    """Tests for the PlanActAgent subclass."""

    def test_planact_generates_and_executes_plan(self):
        """
        PlanActAgent must generate a plan, execute steps, and produce a summary.
        """
        plan_json = json.dumps([
            {"step": "Add numbers", "tool": "add", "args": {"a": 2, "b": 3}},
            {"step": "Report result", "tool": None, "args": {}},
        ])
        llm = MockLLM(responses=[
            plan_json,        # plan generation
            "The sum is 5.",  # final summary
        ])

        agent = PlanActAgent(llm=llm, tools=[make_add_tool()], name="plan_test")
        memory = MEMORY()
        memory.add_msg("user", "Add 2 and 3.")
        memory = agent(memory)

        assert len(agent.execution_log) >= 1
        assert agent.execution_log[0]["success"] is True

    def test_planact_falls_back_on_bad_plan(self):
        """
        PlanActAgent must fall back to base AGENT behavior when plan parsing fails.
        """
        llm = MockLLM(responses=[
            "I can't make a plan for this.",  # bad plan (not JSON)
            "Here is my answer.",             # base agent response
        ])

        agent = PlanActAgent(llm=llm, name="test")
        memory = MEMORY()
        memory.add_msg("user", "Do something.")
        memory = agent(memory)

        assert memory.get_var("test_result") is not None

    def test_planact_stores_execution_log(self):
        """
        PlanActAgent must maintain a log of executed steps.
        """
        plan_json = json.dumps([
            {"step": "Echo hello", "tool": "echo", "args": {"text": "hello"}},
        ])
        llm = MockLLM(responses=[plan_json, "Done."])

        agent = PlanActAgent(llm=llm, tools=[make_echo_tool()], name="test")
        memory = MEMORY()
        memory.add_msg("user", "Echo hello")
        memory = agent(memory)

        assert len(agent.execution_log) == 1
        assert "Echo: hello" in agent.execution_log[0]["result"]


# ============================================================================
# String Representation Tests
# ============================================================================


class TestAgentRepr:
    """Tests for AGENT string representations."""

    def test_agent_str(self):
        """AGENT __str__ must show name and tool count."""
        agent = AGENT(llm=MockLLM(), tools=[make_add_tool()], name="my_agent")
        assert "my_agent" in str(agent)
        assert "1" in str(agent)

    def test_react_str(self):
        """ReactAgent __str__ must identify itself."""
        agent = ReactAgent(llm=MockLLM(), name="react")
        assert "ReactAgent" in str(agent)

    def test_reflect_str(self):
        """ReflectAgent __str__ must identify itself."""
        agent = ReflectAgent(llm=MockLLM(), name="reflect")
        assert "ReflectAgent" in str(agent)

    def test_planact_str(self):
        """PlanActAgent __str__ must identify itself."""
        agent = PlanActAgent(llm=MockLLM(), name="planact")
        assert "PlanActAgent" in str(agent)

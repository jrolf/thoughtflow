"""
Unit tests for the ThoughtFlow AGENT class and its subclasses
(ReactAgent, ReflectAgent, PlanActAgent).

Tests use the MockLLM from conftest to simulate LLM responses without HTTP calls.
"""

from __future__ import annotations

import json


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

    def test_merge_augments_defaults_false(self):
        """AGENT must default merge_augments to False."""
        agent = AGENT(llm=MockLLM(), name="test")
        assert agent.merge_augments is False


class TestAgentMergeAugments:
    """Tests for optional LLM-view augmentation on AGENT (issue #15)."""

    def test_default_forwards_separate_context_message(self):
        """Default AGENT must send augment events as separate LLM messages."""
        llm = MockLLM(responses=["Answer"])
        agent = AGENT(llm=llm, system_prompt="You are helpful.", name="test")
        memory = MEMORY()
        memory.add_msg("user", "Question?")
        memory.add_augment("RAG context", metadata={"internal": True})

        agent(memory)

        sent = llm.calls[0]["msgs"]
        roles = [msg["role"] for msg in sent]
        contents = [msg["content"] for msg in sent]

        assert roles == ["system", "user", "system"]
        assert contents[1] == "Question?"
        assert contents[2] == "RAG context"

    def test_merge_augments_folds_context_into_user_message(self):
        """merge_augments=True must fold augment events into the user LLM message."""
        llm = MockLLM(responses=["Answer"])
        agent = AGENT(
            llm=llm,
            system_prompt="You are helpful.",
            name="test",
            merge_augments=True,
        )
        memory = MEMORY()
        memory.add_msg("user", "Question?")
        memory.add_augment("RAG context", metadata={"internal": True})

        agent(memory)

        sent = llm.calls[0]["msgs"]
        roles = [msg["role"] for msg in sent]
        contents = [msg["content"] for msg in sent]

        assert roles == ["system", "user"]
        assert contents[1] == "RAG context\n\nQuestion?"


class TestParseToolCalls:
    """Tests for AGENT tool-call JSON parsing."""

    def test_parses_json_wrapped_in_markdown_fence(self):
        """AGENT must parse tool calls when the LLM wraps JSON in markdown fences."""
        payload = {"name": "add", "arguments": {"a": 1, "b": 2}}
        fenced = "```json\n{}\n```".format(json.dumps(payload))
        agent = AGENT(llm=MockLLM(), name="test")

        calls = agent._parse_tool_calls(fenced)

        assert calls == [payload]

    def test_preserves_inline_backticks_inside_json(self):
        """Fence stripping must not remove backticks inside JSON string values."""
        payload = {
            "name": "echo",
            "arguments": {"text": "use `backticks` in code"},
        }
        fenced = "```\n{}\n```".format(json.dumps(payload))
        agent = AGENT(llm=MockLLM(), name="test")

        calls = agent._parse_tool_calls(fenced)

        assert calls == [payload]

    def test_plain_json_still_parses(self):
        """AGENT must continue parsing plain JSON responses unchanged."""
        payload = {"name": "add", "arguments": {"a": 3, "b": 4}}
        agent = AGENT(llm=MockLLM(), name="test")

        assert agent._parse_tool_calls(json.dumps(payload)) == [payload]


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

    def test_tool_call_parses_fenced_json_response(self):
        """
        AGENT must execute tools when the LLM returns fenced JSON tool calls.
        """
        tool_call_json = json.dumps({"name": "add", "arguments": {"a": 5, "b": 3}})
        fenced = "```json\n{}\n```".format(tool_call_json)
        llm = MockLLM(responses=[fenced, "The sum is 8."])

        agent = AGENT(llm=llm, tools=[make_add_tool()], name="calc")
        memory = MEMORY()
        memory.add_msg("user", "Add 5 and 3")

        memory = agent(memory)

        assert memory.get_var("calc_result") == "The sum is 8."
        assert llm.call_count == 2

    def test_tool_call_and_response_cycle(self):
        """
        AGENT must execute tools when the LLM requests them, then get a final response.
        """
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

    def test_react_preserves_multiline_final_answer(self):
        """Issue #25: ReactAgent must keep lines after the first in Final Answer."""
        multiline = (
            "Thought: Ready.\n"
            "Final Answer: Line one\n"
            "- bullet a\n"
            "- bullet b"
        )
        llm = MockLLM(responses=[multiline])
        agent = ReactAgent(llm=llm, name="react_ml")
        memory = MEMORY()
        memory.add_msg("user", "List two bullets")
        memory = agent(memory)

        expected = "Line one\n- bullet a\n- bullet b"
        assert memory.get_var("react_ml_result") == expected
        assert memory.last_asst_msg(content_only=True) == expected

    def test_react_reports_vetoed_tool_observation_to_model(self):
        """Issue #25: vetoed tool calls must append an Observation so the model adapts."""
        step1 = (
            "Thought: Try echo.\n"
            "Action: echo\n"
            'Action Input: {"text": "secret"}'
        )
        step2 = "Thought: Tool was blocked.\nFinal Answer: Cannot run echo."
        llm = MockLLM(responses=[step1, step2])
        agent = ReactAgent(
            llm=llm,
            tools=[make_echo_tool()],
            name="react_veto",
            on_tool_call=lambda name, args: False,
        )
        memory = MEMORY()
        memory.add_msg("user", "Run echo")
        memory = agent(memory)

        assert memory.get_var("react_veto_result") == "Cannot run echo."
        second_call_msgs = llm.calls[1]["msgs"]
        assert any(
            "blocked by policy" in m.get("content", "")
            for m in second_call_msgs
        )


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

        # 1 for plan, 1 for execution
        assert len(agent.execution_log) == 2
        assert "Echo: hello" in agent.execution_log[-1]["result"]


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


# ============================================================================
# Native, governed, write-ahead tool loop (#22, #43) and ReflectAgent (#23)
# ============================================================================

import pytest  # noqa: E402

from thoughtflow import tool_loop  # noqa: E402


class ChatScript:
    """Scripted ``llm.chat``: each step is a dict message; records every request."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.requests = []

    def chat(self, messages, tools=None, params=None, stream=False, cancel=None):
        self.requests.append({"messages": [dict(m) for m in messages], "tools": tools})
        step = self.steps[min(len(self.requests), len(self.steps)) - 1]
        return dict(step)


def calls_msg(*calls, usage=None):
    """Assistant message asking for tool calls: each call is (id, name, arguments)."""
    return {
        "content": "",
        "tool_calls": [
            {"id": cid, "name": name, "arguments": args,
             "raw_arguments": json.dumps(args), "arguments_error": None}
            for cid, name, args in calls
        ],
        "finish_reason": "tool_calls",
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
    }


def final_msg(text):
    return {"content": text, "tool_calls": [], "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def make_counting_tool(name="refund", log=None):
    log = log if log is not None else []

    def fn(amount=0):
        log.append(amount)
        return {"refunded": amount}

    tool = TOOL(name, "Refund money", {"amount": {"type": "number"}}, fn)
    return tool, log


def user_memory(text="Refund me"):
    memory = MEMORY()
    memory.add_msg("user", text)
    return memory


class TestNativeToolLoop:
    def test_runs_tool_and_finishes_with_valid_transcript(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 5})), final_msg("Done")])
        memory = AGENT(llm=llm, tools=[tool], name="a")(user_memory())
        assert log == [5]
        assert memory.get_var("a_status") == "final"
        assert memory.get_var("a_result") == "Done"
        roles = [m["role"] for m in memory.get_msgs(include=["user", "assistant", "tool"])]
        assert roles == ["user", "assistant", "tool", "assistant"]
        second = llm.requests[1]["messages"]
        assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
        assert second[-2]["tool_calls"][0]["function"]["name"] == "refund"

    def test_write_ahead_and_checkpoint_order(self):
        seen = []

        def checkpoint(mem):
            seen.append([m["role"] for m in mem.get_msgs(include=["assistant", "tool"])])

        tool, _ = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 1})), final_msg("ok")])
        AGENT(llm=llm, tools=[tool], checkpoint=checkpoint)(user_memory())
        assert seen[0] == ["assistant"]
        assert seen[1] == ["assistant", "tool"]

    def test_crash_mid_tools_resumes_without_rerunning_answered_calls(self):
        tool, log = make_counting_tool()
        memory = user_memory()
        memory.add_msg("assistant", "", tool_calls=[
            {"id": "c1", "name": "refund", "arguments": {"amount": 1}},
            {"id": "c2", "name": "refund", "arguments": {"amount": 2}},
        ])
        memory.add_msg("tool", "{}", tool_call_id="c1", name="refund")
        llm = ChatScript([final_msg("done")])
        AGENT(llm=llm, tools=[tool], name="r")(memory)
        assert log == [2]

    def test_unknown_tool_allow_list_and_bad_arguments_get_answers(self):
        tool, log = make_counting_tool()
        bad = calls_msg(("c3", "refund", {}))
        bad["tool_calls"][0]["arguments_error"] = "bad json"
        llm = ChatScript([
            calls_msg(("c1", "ghost", {}), ("c2", "refund", {"amount": 1})),
            bad,
            final_msg("ok"),
        ])
        memory = AGENT(llm=llm, tools=[tool], allow=["other"], name="g")(user_memory())
        answers = {m["tool_call_id"]: m["content"] for m in memory.get_msgs(include=["tool"])}
        assert set(answers) == {"c1", "c2", "c3"}
        assert "not available" in answers["c1"] and "not available" in answers["c2"]
        assert "invalid arguments" in answers["c3"]
        assert log == []

    def test_max_iterations_status(self):
        tool, _ = make_counting_tool()
        # Id-less calls get fresh ids each turn, so the loop keeps asking for tools.
        step = calls_msg(("x", "refund", {"amount": 1}))
        step["tool_calls"][0]["id"] = ""
        llm = ChatScript([step])
        memory = AGENT(llm=llm, tools=[tool], max_iterations=2, name="m")(user_memory())
        assert memory.get_var("m_status") == "max_iterations"


class TestGovernance:
    def test_deny_policy_answers_call_and_model_recovers(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 9})), final_msg("sorry")])
        memory = AGENT(llm=llm, tools=[tool], policy={"refund": "deny"}, name="d")(user_memory())
        assert log == []
        assert memory.get_msgs(include=["tool"])[0]["content"].startswith("Denied")
        assert memory.get_var("d_outcome")["vetoed"] == 1
        assert memory.get_var("d_status") == "final"

    def test_halting_deny_ends_as_vetoed(self):
        tool, _ = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {}), ("c2", "refund", {}))])
        memory = AGENT(
            llm=llm, tools=[tool], name="h",
            policy={"refund": {"mode": "deny", "halt": True}},
        )(user_memory())
        assert memory.get_var("h_status") == "vetoed"
        assert {m["tool_call_id"] for m in memory.get_msgs(include=["tool"])} == {"c1", "c2"}

    def test_approve_over_suspends_then_resumes_after_rehydrate(self):
        tool, log = make_counting_tool()
        policy = {"refund": {"mode": "approve_over", "field": "amount", "limit": 100}}
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 500})), final_msg("Refunded")])
        memory = AGENT(llm=llm, tools=[tool], policy=policy, name="s")(user_memory())
        assert memory.get_var("s_status") == "suspended"
        assert memory.is_suspended() and log == []

        restored = MEMORY.from_json(memory.to_json())
        agent = AGENT(llm=llm, tools=[tool], policy=policy, name="s")
        assert agent(restored).get_var("s_status") == "suspended"  # no decision: still waiting
        restored = agent(restored, decision={"approve": True})
        assert log == [500]
        assert restored.get_var("s_status") == "final"
        assert not restored.is_suspended()

    def test_small_amount_runs_without_approval(self):
        tool, log = make_counting_tool()
        policy = {"refund": {"mode": "approve_over", "field": "amount", "limit": 100}}
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 5})), final_msg("ok")])
        AGENT(llm=llm, tools=[tool], policy=policy, name="p")(user_memory())
        assert log == [5]

    def test_rejected_approval_answers_call_without_running(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 1})), final_msg("understood")])
        agent = AGENT(llm=llm, tools=[tool], policy={"refund": "approve"}, name="r")
        memory = agent(user_memory())
        memory = agent(memory, decision={"approve": False})
        assert log == []
        assert memory.get_msgs(include=["tool"])[0]["content"].startswith("Denied")
        assert memory.get_var("r_status") == "final"

    def test_duplicate_decision_does_not_double_execute(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 1})), final_msg("ok")])
        agent = AGENT(llm=llm, tools=[tool], policy={"refund": "approve"}, name="i")
        memory = agent(user_memory())
        agent(memory, decision={"approve": True})
        agent(memory, decision={"approve": True})
        assert log == [1]

    def test_tool_budget_answers_every_call_and_stops(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 1}), ("c2", "refund", {"amount": 2}))])
        memory = AGENT(llm=llm, tools=[tool], budget={"max_tool_calls": 1}, name="b")(user_memory())
        assert log == [1]
        assert memory.get_var("b_status") == "budget_exhausted"
        assert {m["tool_call_id"] for m in memory.get_msgs(include=["tool"])} == {"c1", "c2"}

    def test_model_call_budget(self):
        tool, _ = make_counting_tool()
        step = calls_msg(("x", "refund", {"amount": 1}))
        step["tool_calls"][0]["id"] = ""
        memory = AGENT(
            llm=ChatScript([step]), tools=[tool], budget={"max_model_calls": 2}, name="mb"
        )(user_memory())
        assert memory.get_var("mb_status") == "budget_exhausted"
        assert memory.get_var("mb_outcome")["model_calls"] == 2

    def test_token_budget_stops_at_limit(self):
        tool, _ = make_counting_tool()
        step = calls_msg(("x", "refund", {"amount": 1}), usage={"prompt_tokens": 40, "completion_tokens": 10})
        step["tool_calls"][0]["id"] = ""
        memory = AGENT(
            llm=ChatScript([step]), tools=[tool], budget={"max_tokens": 100}, name="tb"
        )(user_memory())
        assert memory.get_var("tb_status") == "budget_exhausted"
        assert memory.get_var("tb_outcome")["model_calls"] == 2

    def test_counters_survive_resolved_suspension_then_interrupted_run(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 1})), final_msg("ok")])
        agent = AGENT(llm=llm, tools=[tool], policy={"refund": "approve"}, name="cs")
        memory = agent(user_memory())
        memory.resolve_suspension({"approve": True})  # resolved, then the process died
        assert memory.get_var("cs_outcome")["status"] == "suspended"
        memory = agent(memory, decision={"approve": True})
        assert log == [1]
        assert memory.get_var("cs_outcome")["model_calls"] == 2

    def test_wire_format_pending_calls_resume(self):
        tool, log = make_counting_tool()
        memory = user_memory()
        memory.add_msg("assistant", "", tool_calls=[{
            "id": "w1", "type": "function",
            "function": {"name": "refund", "arguments": "{\"amount\": 7}"},
        }])
        AGENT(llm=ChatScript([final_msg("done")]), tools=[tool], name="wf")(memory)
        assert log == [7]

    def test_governance_without_chat_is_rejected(self):
        with pytest.raises(ValueError):
            AGENT(llm=MockLLM(), policy={"x": "deny"})(user_memory())

    def test_tool_loop_helper_delegates(self):
        tool, log = make_counting_tool()
        llm = ChatScript([calls_msg(("c1", "refund", {"amount": 3})), final_msg("ok")])
        memory = tool_loop(user_memory(), llm, [tool], name="t")
        assert log == [3] and memory.get_var("t_status") == "final"

    def test_text_protocol_still_default_for_call_only_llms(self):
        llm = MockLLM(responses=["plain answer"])
        memory = AGENT(llm=llm, name="legacy")(user_memory("hi"))
        assert memory.get_var("legacy_result") == "plain answer"


class TestToolContext:
    def test_needs_context_tool_receives_call_context(self):
        seen = {}

        def fn(path, context=None):
            seen.update(context)
            return "ok"

        tool = TOOL("read", "Read", {"path": {"type": "string"}}, fn, needs_context=True)
        llm = ChatScript([calls_msg(("c9", "read", {"path": "a"})), final_msg("done")])
        memory = AGENT(llm=llm, tools=[tool], name="cx")(user_memory())
        assert seen["call_id"] == "c9" and seen["memory"] is memory
        assert "context" not in json.dumps(tool.to_schema())

    def test_direct_call_passes_none_context(self):
        tool = TOOL("t", "T", {}, lambda context=None: context, needs_context=True)
        assert tool({}) is None

    def test_from_action_receives_memory(self):
        from thoughtflow import ACTION

        action = ACTION(name="note", fn=lambda memory, text="": memory.add_log(text) or "logged")
        tool = TOOL.from_action(action, parameters={"text": {"type": "string"}})
        memory = MEMORY()
        assert tool({"text": "hi"}, context={"memory": memory}) == "logged"
        assert any("hi" in log["content"] for log in memory.get_logs())

    def test_needs_context_round_trips_to_dict(self):
        tool = TOOL("t", "T", {}, lambda context=None: 1, needs_context=True)
        data = tool.to_dict()
        clone = TOOL.from_dict(data, {data["fn_name"]: tool.fn})
        assert clone.needs_context is True


class TestReflectFixes:
    def test_critic_sees_task_and_negation_is_not_approval(self):
        llm = MockLLM(responses=["Draft.", "This is not approved: too vague.", "Better.", "APPROVED"])
        agent = ReflectAgent(llm=llm, name="rf", max_revisions=2)
        memory = user_memory("Explain gravity")
        memory = agent(memory)
        assert "Explain gravity" in llm.calls[1]["msgs"][0]["content"]
        assert memory.get_var("rf_result") == "Better."
        assert memory.last_asst_msg(content_only=True) == "Better."
        assert memory.get_var("rf_outcome")["approved"] is True

    def test_custom_prompt_with_only_response_still_works(self):
        llm = MockLLM(responses=["Draft.", "APPROVED"])
        agent = ReflectAgent(llm=llm, critique_prompt="Judge: {response}", name="rc")
        agent(user_memory("q"))
        assert llm.calls[1]["msgs"][0]["content"] == "Judge: Draft."

    def test_final_verification_recorded_when_revisions_exhausted(self):
        llm = MockLLM(responses=["Draft.", "needs improvement", "Second.", "APPROVED"])
        agent = ReflectAgent(llm=llm, name="fv", max_revisions=1)
        memory = agent(user_memory("q"))
        outcome = memory.get_var("fv_outcome")
        assert outcome["approved"] is True and outcome["revisions"] == 1
        assert len(agent.revision_history) == 1

    def test_should_approve_negation_safe(self):
        agent = ReflectAgent(llm=MockLLM(), name="n")
        assert agent._should_approve("APPROVED")
        assert not agent._should_approve("Not approved yet")
        assert not agent._should_approve("I cannot approve this; revise it")
        assert agent._should_approve("Looks good to me")
        assert not agent._should_approve("This is unapproved")
        assert not agent._should_approve("Disapproved.")


class TestProtocolAutoUnsupportedService:
    def test_llm_with_unsupported_service_uses_text_loop(self):
        class AnthropicLike:
            service = "anthropic"
            model = "m"

            def chat(self, *args, **kwargs):
                raise ValueError("LLM.chat supports the openai, openrouter and groq services")

            def call(self, msgs, params=None):
                return ["plain text answer"]

        memory = AGENT(llm=AnthropicLike(), name="an")(user_memory("hi"))
        assert memory.get_var("an_result") == "plain text answer"

    def test_governance_with_unsupported_service_is_rejected(self):
        class OllamaLike:
            service = "ollama"

            def chat(self, *args, **kwargs):
                raise ValueError("unsupported")

        with pytest.raises(ValueError):
            AGENT(llm=OllamaLike(), policy={"x": "deny"})(user_memory())

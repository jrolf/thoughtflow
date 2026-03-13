"""
Unit tests for the ThoughtFlow DELEGATE class.

DELEGATE coordinates work between multiple agents using three modes:
- handoff (fire-and-forget)
- dispatch (request-response)
- broadcast (fan-out)

Tests use mock agents (callables) that simulate AGENT behavior.
"""

from __future__ import annotations

import pytest

from thoughtflow.delegate import DELEGATE
from thoughtflow import MEMORY


# ============================================================================
# Helpers
# ============================================================================


class MockAgent:
    """
    A mock agent that stores a response in memory when called.

    Simulates the AGENT contract: memory = agent(memory).
    """

    def __init__(self, name, response="Mock response"):
        self.name = name
        self.response = response
        self.call_count = 0

    def __call__(self, memory):
        self.call_count += 1
        memory.add_msg("assistant", self.response)
        memory.set_var("{}_result".format(self.name), self.response)
        return memory


# ============================================================================
# Initialization Tests
# ============================================================================


class TestDelegateInitialization:
    """Tests for DELEGATE initialization."""

    def test_registers_agents_by_name(self):
        """
        DELEGATE must build a name->agent lookup from the agents list.

        Remove this test if: We change agent registration.
        """
        agent_a = MockAgent("alpha")
        agent_b = MockAgent("beta")

        delegate = DELEGATE(agents=[agent_a, agent_b])

        assert "alpha" in delegate.agents
        assert "beta" in delegate.agents

    def test_generates_unique_id(self):
        """DELEGATE must have a unique ID."""
        d1 = DELEGATE(name="d1")
        d2 = DELEGATE(name="d2")
        assert d1.id != d2.id

    def test_empty_agents_list(self):
        """DELEGATE must handle empty/no agents gracefully."""
        delegate = DELEGATE()
        assert delegate.agents == {}


# ============================================================================
# Handoff Tests
# ============================================================================


class TestDelegateHandoff:
    """Tests for DELEGATE.handoff() — fire-and-forget delegation."""

    def test_handoff_calls_target_agent(self):
        """
        handoff() must call the target agent with a copy of memory.

        Remove this test if: We change handoff behavior.
        """
        agent = MockAgent("worker", response="I'm working on it.")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()
        memory.add_msg("user", "Original context")

        result_memory = delegate.handoff(memory, "worker", "Do the task")

        assert agent.call_count == 1
        assert result_memory.get_var("worker_result") == "I'm working on it."

    def test_handoff_does_not_mutate_original(self):
        """
        handoff() must not modify the original memory.

        Remove this test if: We change handoff to modify the original.
        """
        agent = MockAgent("worker")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()
        memory.add_msg("user", "Original")

        delegate.handoff(memory, "worker", "Extra task")

        # Original memory should not have the "Extra task" message
        msgs = memory.get_msgs()
        contents = [m.get("content", "") for m in msgs]
        assert "Extra task" not in contents

    def test_handoff_adds_task_to_copy(self):
        """
        handoff() must add the task as a user message to the copied memory.

        Remove this test if: We change task injection.
        """
        received_msgs = []

        class CapturingAgent:
            name = "capturer"

            def __call__(self, memory):
                for m in memory.get_msgs():
                    received_msgs.append(m.get("content", ""))
                memory.set_var("capturer_result", "done")
                return memory

        delegate = DELEGATE(agents=[CapturingAgent()])
        memory = MEMORY()
        memory.add_msg("user", "Base context")

        delegate.handoff(memory, "capturer", "Special instruction")

        assert "Special instruction" in received_msgs

    def test_handoff_raises_on_unknown_agent(self):
        """
        handoff() must raise KeyError for unregistered agents.

        Remove this test if: We change error handling.
        """
        delegate = DELEGATE()

        with pytest.raises(KeyError, match="unknown"):
            delegate.handoff(MEMORY(), "unknown")

    def test_handoff_logs_event(self):
        """
        handoff() must record the delegation in the log.

        Remove this test if: We remove delegation logging.
        """
        agent = MockAgent("worker")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()

        delegate.handoff(memory, "worker")

        assert len(delegate.delegation_log) == 1
        assert delegate.delegation_log[0]["mode"] == "handoff"


# ============================================================================
# Dispatch Tests
# ============================================================================


class TestDelegateDispatch:
    """Tests for DELEGATE.dispatch() — request-response delegation."""

    def test_dispatch_returns_result_in_memory(self):
        """
        dispatch() must store the agent's result in the original memory.

        Remove this test if: We change dispatch result handling.
        """
        agent = MockAgent("researcher", response="Found relevant data.")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()
        memory.add_msg("user", "Find info on X")

        memory = delegate.dispatch(memory, "researcher", "Search for X")

        assert memory.get_var("researcher_dispatch_result") == "Found relevant data."

    def test_dispatch_calls_agent(self):
        """
        dispatch() must actually call the target agent.

        Remove this test if: We change dispatch behavior.
        """
        agent = MockAgent("worker")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()

        delegate.dispatch(memory, "worker", "Do something")

        assert agent.call_count == 1

    def test_dispatch_does_not_mutate_original_messages(self):
        """
        dispatch() must not add the task to the original memory's messages.

        Remove this test if: We change isolation model.
        """
        agent = MockAgent("worker")
        delegate = DELEGATE(agents=[agent])
        memory = MEMORY()
        memory.add_msg("user", "Original")

        delegate.dispatch(memory, "worker", "Side task")

        msgs = memory.get_msgs()
        contents = [m.get("content", "") for m in msgs]
        assert "Side task" not in contents

    def test_dispatch_raises_on_unknown_agent(self):
        """dispatch() must raise KeyError for unregistered agents."""
        delegate = DELEGATE()

        with pytest.raises(KeyError):
            delegate.dispatch(MEMORY(), "missing")

    def test_dispatch_logs_event(self):
        """dispatch() must record the delegation in the log."""
        agent = MockAgent("worker")
        delegate = DELEGATE(agents=[agent])

        delegate.dispatch(MEMORY(), "worker")

        assert delegate.delegation_log[-1]["mode"] == "dispatch"


# ============================================================================
# Broadcast Tests
# ============================================================================


class TestDelegateBroadcast:
    """Tests for DELEGATE.broadcast() — fan-out delegation."""

    def test_broadcast_calls_all_agents(self):
        """
        broadcast() must call all registered agents.

        Remove this test if: We change broadcast behavior.
        """
        agent_a = MockAgent("alpha", response="Alpha result")
        agent_b = MockAgent("beta", response="Beta result")
        delegate = DELEGATE(agents=[agent_a, agent_b])
        memory = MEMORY()

        memory = delegate.broadcast(memory, "Summarize")

        assert agent_a.call_count == 1
        assert agent_b.call_count == 1

    def test_broadcast_collects_results(self):
        """
        broadcast() must collect results from all agents into a dict.

        Remove this test if: We change result collection.
        """
        agent_a = MockAgent("alpha", response="Alpha result")
        agent_b = MockAgent("beta", response="Beta result")
        delegate = DELEGATE(agents=[agent_a, agent_b])
        memory = MEMORY()

        memory = delegate.broadcast(memory, "Summarize")

        results = memory.get_var("delegate_broadcast_results")
        assert results["alpha"] == "Alpha result"
        assert results["beta"] == "Beta result"

    def test_broadcast_specific_agents(self):
        """
        broadcast() must only call specified agents when agent_names is given.

        Remove this test if: We change broadcast targeting.
        """
        agent_a = MockAgent("alpha")
        agent_b = MockAgent("beta")
        delegate = DELEGATE(agents=[agent_a, agent_b])
        memory = MEMORY()

        memory = delegate.broadcast(memory, "Task", agent_names=["alpha"])

        assert agent_a.call_count == 1
        assert agent_b.call_count == 0

    def test_broadcast_handles_missing_agent(self):
        """
        broadcast() must include an error for unknown agent names.

        Remove this test if: We change missing agent handling.
        """
        delegate = DELEGATE(agents=[MockAgent("alpha")])
        memory = MEMORY()

        memory = delegate.broadcast(memory, "Task", agent_names=["alpha", "missing"])

        results = memory.get_var("delegate_broadcast_results")
        assert "missing" in results
        assert "Error" in results["missing"]

    def test_broadcast_logs_event(self):
        """broadcast() must record the delegation in the log."""
        delegate = DELEGATE(agents=[MockAgent("alpha")])
        memory = MEMORY()

        delegate.broadcast(memory, "Task")

        assert delegate.delegation_log[-1]["mode"] == "broadcast"


# ============================================================================
# String Representation Tests
# ============================================================================


class TestDelegateRepr:
    """Tests for DELEGATE string representations."""

    def test_str(self):
        """DELEGATE __str__ must show name and agent names."""
        delegate = DELEGATE(agents=[MockAgent("a"), MockAgent("b")], name="coord")
        s = str(delegate)
        assert "coord" in s
        assert "a" in s

    def test_repr(self):
        """DELEGATE __repr__ must show name, agents, and delegation count."""
        delegate = DELEGATE(agents=[MockAgent("a")], name="coord")
        r = repr(delegate)
        assert "coord" in r

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


class TestDelegateMemoryCopyFidelity:
    """Regression coverage for issue #18: DELEGATE._copy_memory variable fidelity."""

    def test_dispatch_preserves_scalar_vars_descriptions_and_tombstones(self):
        captured = {}

        class ReadingAgent:
            name = "specialist"

            def __call__(self, mem):
                captured["customer_id"] = mem.get_var("customer_id")
                captured["desc"] = mem.get_var_desc("customer_id")
                captured["deleted"] = mem.is_var_deleted("old_token")
                mem.set_var("specialist_result", "handled {}".format(captured["customer_id"]))
                return mem

        memory = MEMORY()
        memory.set_var("customer_id", "C-77", desc="Primary customer")
        memory.set_var("old_token", "secret")
        memory.del_var("old_token")

        delegate = DELEGATE(agents=[ReadingAgent()])
        memory = delegate.dispatch(memory, "specialist", "Check account")

        assert captured["customer_id"] == "C-77"
        assert captured["desc"] == "Primary customer"
        assert captured["deleted"] is True
        assert memory.get_var("specialist_dispatch_result") == "handled C-77"


class TestDelegateOutcomesDispatchManyAndMapThought:
    """Tests for #41 (callable dicts, per-agent outcomes, merge-back) and #45 (dispatch_many, parallel broadcast, map_thought)."""

    def test_callable_dict_outcomes_and_merge_back(self):
        def billing_fn(mem):
            mem.set_var("invoice_id", "INV-9")
            mem.add_msg("assistant", "Checked invoice INV-9")
            mem.emit("usage", {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001})
            mem.set_var("billing_result", "Refund approved")
            return mem

        def broken_logistics(mem):
            raise RuntimeError("warehouse API down")

        delegate = DELEGATE(agents={"billing": billing_fn, "logistics": broken_logistics})
        mem = MEMORY()
        mem = delegate.dispatch(mem, "billing", "Check double charge", merge_vars=["invoice_id"], merge_msgs=True)

        assert mem.get_var("billing_dispatch_result") == "Refund approved"
        b_out = mem.get_var("billing_dispatch_outcome")
        assert b_out["ok"] is True
        assert b_out["usage"]["total_tokens"] == 15
        assert mem.get_var("invoice_id") == "INV-9"
        assert mem.last_asst_msg(content_only=True) == "Checked invoice INV-9"

        # Parallel broadcast captures both success and specialist error without crashing
        mem = delegate.broadcast(mem, "Status check", parallel=True)
        outcomes = mem.get_var("delegate_broadcast_outcomes")
        assert outcomes["billing"]["ok"] is True
        assert outcomes["logistics"]["ok"] is False
        assert "warehouse API down" in outcomes["logistics"]["error"]

    def test_dispatch_many_parallel_preserves_assignment_order(self):
        import time

        def slow_fn(mem):
            time.sleep(0.03)
            return "slow:" + (mem.last_user_msg(content_only=True) or "")

        def fast_fn(mem):
            return "fast:" + (mem.last_user_msg(content_only=True) or "")

        delegate = DELEGATE(agents={"slow": slow_fn, "fast": fast_fn})
        mem = MEMORY()
        reports = delegate.dispatch_many(
            mem,
            [
                {"agent": "slow", "task": "A"},
                {"agent": "fast", "task": "B"},
            ],
            parallel=True,
        )

        assert [r["agent"] for r in reports] == ["slow", "fast"]
        assert reports[0]["ok"] is True and reports[0]["result"] == "slow:A"
        assert reports[1]["ok"] is True and reports[1]["result"] == "fast:B"

    def test_map_thought_voting_and_items_parallel(self):
        from thoughtflow import THOUGHT, map_thought

        class EchoVarsLLM:
            last_error = None
            last_finish_reason = "stop"
            last_usage = {"prompt_tokens": 4, "completion_tokens": 2}

            def call(self, msgs, params=None):
                return [msgs[-1]["content"].upper()]

        step = THOUGHT(
            name="upper",
            llm=EchoVarsLLM(),
            prompt="Item={item}",
            include_history=False,
        )
        base_mem = MEMORY()

        item_outcomes = map_thought(step, base_mem, items=["one", "two", "three"], parallel=True)
        assert [o["result"] for o in item_outcomes] == ["ITEM=ONE", "ITEM=TWO", "ITEM=THREE"]
        assert all(o["ok"] for o in item_outcomes)
        assert base_mem.get_var("item") is None  # base memory untouched

        vote_step = THOUGHT(name="vote", llm=EchoVarsLLM(), prompt="Vote", include_history=False)
        vote_outcomes = map_thought(vote_step, base_mem, n=4, parallel=True)
        assert len(vote_outcomes) == 4
        assert [o["index"] for o in vote_outcomes] == [0, 1, 2, 3]
        assert all(o["result"] == "VOTE" for o in vote_outcomes)


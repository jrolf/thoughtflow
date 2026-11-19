"""
Unit tests for the ThoughtFlow WORKFLOW class.

WORKFLOW provides lightweight step-based orchestration with conditional
branching, error handling, and execution tracking.
"""

from __future__ import annotations


from thoughtflow.workflow import WORKFLOW
from thoughtflow import MEMORY


# ============================================================================
# Helpers
# ============================================================================


def step_set_flag(memory):
    """A step that sets a flag variable."""
    memory.set_var("flag", True)
    return memory


def step_increment(memory):
    """A step that increments a counter."""
    current = memory.get_var("counter") or 0
    memory.set_var("counter", current + 1)
    return memory


def step_failing(memory):
    """A step that always raises an error."""
    raise RuntimeError("Step failed intentionally.")


def step_add_msg(memory):
    """A step that adds an assistant message."""
    memory.add_msg("assistant", "Workflow step completed.")
    return memory


# ============================================================================
# Initialization Tests
# ============================================================================


class TestWorkflowInitialization:
    """Tests for WORKFLOW initialization."""

    def test_stores_name(self):
        """WORKFLOW must store the provided name."""
        wf = WORKFLOW(name="my_flow")
        assert wf.name == "my_flow"

    def test_generates_unique_id(self):
        """Each WORKFLOW must have a unique ID."""
        wf1 = WORKFLOW(name="a")
        wf2 = WORKFLOW(name="b")
        assert wf1.id != wf2.id

    def test_starts_with_no_steps(self):
        """WORKFLOW must start with an empty steps list."""
        wf = WORKFLOW()
        assert wf.steps == []

    def test_default_on_error_is_stop(self):
        """WORKFLOW must default to 'stop' error handling."""
        wf = WORKFLOW()
        assert wf.on_error == "stop"


# ============================================================================
# Step Registration Tests
# ============================================================================


class TestWorkflowSteps:
    """Tests for WORKFLOW step registration."""

    def test_adds_step(self):
        """step() must add a step to the workflow."""
        wf = WORKFLOW()
        wf.step(step_set_flag, name="set_flag")

        assert len(wf.steps) == 1
        assert wf.steps[0]["name"] == "set_flag"

    def test_step_chaining(self):
        """step() must return self for method chaining."""
        wf = WORKFLOW()
        result = wf.step(step_set_flag).step(step_increment)

        assert result is wf
        assert len(wf.steps) == 2

    def test_step_uses_function_name_as_default(self):
        """step() must use fn.__name__ when no name is given."""
        wf = WORKFLOW()
        wf.step(step_set_flag)

        assert wf.steps[0]["name"] == "step_set_flag"


# ============================================================================
# Execution Tests
# ============================================================================


class TestWorkflowExecution:
    """Tests for WORKFLOW execution behavior."""

    def test_executes_steps_in_order(self):
        """
        WORKFLOW must execute steps in the order they were added.
        """
        wf = WORKFLOW(name="test")
        wf.step(step_set_flag, name="set_flag")
        wf.step(step_increment, name="increment")

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("flag") is True
        assert memory.get_var("counter") == 1

    def test_returns_memory(self):
        """
        WORKFLOW must return the memory instance (contract: memory = wf(memory)).
        """
        wf = WORKFLOW()
        wf.step(step_set_flag)

        memory = MEMORY()
        result = wf(memory)

        assert result is memory

    def test_records_execution_log(self):
        """
        WORKFLOW must record execution timing and status for each step.
        """
        wf = WORKFLOW()
        wf.step(step_set_flag, name="flag")
        wf.step(step_increment, name="counter")

        memory = MEMORY()
        wf(memory)

        assert len(wf.execution_log) == 2
        assert wf.execution_log[0]["step"] == "flag"
        assert wf.execution_log[0]["status"] == "completed"
        assert "duration_ms" in wf.execution_log[0]

    def test_stores_status_in_memory(self):
        """
        WORKFLOW must store execution status in memory after completion.
        """
        wf = WORKFLOW(name="test_flow")
        wf.step(step_set_flag)

        memory = MEMORY()
        memory = wf(memory)

        status = memory.get_var("test_flow_status")
        assert status["total_steps"] == 1
        assert status["completed"] == 1


# ============================================================================
# Conditional Step Tests
# ============================================================================


class TestWorkflowConditions:
    """Tests for conditional step execution."""

    def test_runs_step_when_condition_true(self):
        """
        WORKFLOW must execute a step when its condition returns True.
        """
        wf = WORKFLOW()
        wf.step(step_set_flag, name="flag")
        wf.step(step_increment, name="inc", condition=lambda m: m.get_var("flag") is True)

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("counter") == 1

    def test_skips_step_when_condition_false(self):
        """
        WORKFLOW must skip a step when its condition returns False.
        """
        wf = WORKFLOW()
        wf.step(step_increment, name="inc", condition=lambda m: False)

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("counter") is None

    def test_logs_skipped_steps(self):
        """
        WORKFLOW must record skipped steps in the execution log.
        """
        wf = WORKFLOW()
        wf.step(step_increment, name="skipped", condition=lambda m: False)

        memory = MEMORY()
        wf(memory)

        assert wf.execution_log[0]["status"] == "skipped"

    def test_condition_exception_records_error_and_honors_on_error(self):
        """Issue #27: buggy condition callables must fail the step, not skip as False."""
        def broken_cond(m):
            raise ZeroDivisionError("bad guard")

        wf_stop = WORKFLOW(name="wf_stop", on_error="stop")
        wf_stop.step(step_increment, name="guarded", condition=broken_cond)
        wf_stop.step(step_set_flag, name="after")

        mem1 = wf_stop(MEMORY())
        assert wf_stop.execution_log[0]["status"] == "error"
        assert "bad guard" in wf_stop.execution_log[0]["error"]
        assert mem1.get_var("flag") is None

        wf_skip = WORKFLOW(name="wf_skip", on_error="skip")
        wf_skip.step(step_increment, name="guarded", condition=broken_cond)
        wf_skip.step(step_set_flag, name="after")

        mem2 = wf_skip(MEMORY())
        assert wf_skip.execution_log[0]["status"] == "error"
        assert mem2.get_var("flag") is True


# ============================================================================
# Branch Tests
# ============================================================================


class TestWorkflowBranching:
    """Tests for WORKFLOW branching."""

    def test_branch_routes_correctly(self):
        """
        branch() must execute the callable matching the router's return value.
        """
        def set_a(m):
            m.set_var("branch", "A")
            return m

        def set_b(m):
            m.set_var("branch", "B")
            return m

        wf = WORKFLOW()
        wf.step(lambda m: (m.set_var("route", "B") or m), name="setup")
        wf.branch(
            router_fn=lambda m: m.get_var("route"),
            branches={"A": set_a, "B": set_b},
            name="router",
        )

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("branch") == "B"

    def test_branch_uses_default(self):
        """
        branch() must use the 'default' branch when key is not found.
        """
        def default_handler(m):
            m.set_var("branch", "default")
            return m

        wf = WORKFLOW()
        wf.branch(
            router_fn=lambda m: "unknown",
            branches={"default": default_handler},
            name="router",
        )

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("branch") == "default"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestWorkflowErrors:
    """Tests for WORKFLOW error handling."""

    def test_stop_on_error(self):
        """
        WORKFLOW must stop on first error when on_error='stop'.
        """
        wf = WORKFLOW(on_error="stop")
        wf.step(step_failing, name="fail")
        wf.step(step_set_flag, name="never_reached")

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("flag") is None
        assert wf.execution_log[0]["status"] == "error"
        assert len(wf.execution_log) == 1

    def test_skip_on_error(self):
        """
        WORKFLOW must skip failed steps and continue when on_error='skip'.
        """
        wf = WORKFLOW(on_error="skip")
        wf.step(step_failing, name="fail")
        wf.step(step_set_flag, name="should_run")

        memory = MEMORY()
        memory = wf(memory)

        assert memory.get_var("flag") is True
        assert wf.execution_log[0]["status"] == "error"
        assert wf.execution_log[1]["status"] == "completed"

    def test_retry_on_error(self):
        """
        WORKFLOW must retry a failed step once when on_error='retry'.
        If retry fails, it stops.
        """
        wf = WORKFLOW(on_error="retry")
        wf.step(step_failing, name="always_fails")
        wf.step(step_set_flag, name="never_reached")

        memory = MEMORY()
        memory = wf(memory)

        # Should have error + retry_failed
        error_statuses = [e["status"] for e in wf.execution_log]
        assert "error" in error_statuses
        assert "retry_failed" in error_statuses
        assert memory.get_var("flag") is None


# ============================================================================
# String Representation Tests
# ============================================================================


class TestWorkflowRepr:
    """Tests for WORKFLOW string representations."""

    def test_str(self):
        """WORKFLOW __str__ must show name and step names."""
        wf = WORKFLOW(name="my_flow")
        wf.step(step_set_flag, name="flag")
        assert "my_flow" in str(wf)
        assert "flag" in str(wf)

    def test_repr(self):
        """WORKFLOW __repr__ must show name, step count, and error mode."""
        wf = WORKFLOW(name="my_flow", on_error="skip")
        wf.step(step_set_flag)
        r = repr(wf)
        assert "my_flow" in r
        assert "skip" in r


# ============================================================================
# ok predicate, status branching, bounded loops, suspend/resume (#52, #44)
# ============================================================================


class _Named:
    """Callable step with a ``name`` that writes an outcome like THOUGHT does."""

    def __init__(self, name, ok):
        self.name = name
        self.ok = ok

    def __call__(self, memory):
        memory.set_var("{}_outcome".format(self.name), {"ok": self.ok})
        return memory


class TestOkPredicate:
    def test_auto_reads_outcome_and_marks_degraded(self):
        wf = WORKFLOW("w", on_error="stop")
        wf.step(_Named("bad", ok=False), ok="auto")
        wf.step(step_increment, name="after")
        memory = wf(MEMORY())
        assert wf.execution_log[0]["status"] == "degraded"
        assert memory.get_var("counter") is None
        assert memory.get_var("w_status")["degraded"] == 1

    def test_degraded_with_skip_continues(self):
        wf = WORKFLOW("w", on_error="skip")
        wf.step(_Named("bad", ok=False), ok="auto")
        wf.step(step_increment, name="after")
        memory = wf(MEMORY())
        assert memory.get_var("counter") == 1

    def test_custom_predicate_and_passing_auto(self):
        wf = WORKFLOW("w")
        wf.step(_Named("good", ok=True), ok="auto")
        wf.step(step_increment, name="inc", ok=lambda m: m.get_var("counter") == 1)
        wf(MEMORY())
        assert [e["status"] for e in wf.execution_log] == ["completed", "completed"]

    def test_retry_reruns_degraded_step(self):
        calls = []

        def flaky(memory):
            calls.append(1)
            memory.set_var("good", len(calls) > 1)
            return memory

        wf = WORKFLOW("w", on_error="retry")
        wf.step(flaky, name="flaky", ok=lambda m: m.get_var("good"))
        wf(MEMORY())
        assert wf.execution_log[-1]["status"] == "completed_on_retry"

    def test_invalid_ok_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            WORKFLOW("w").step(step_increment, ok="nope")


class TestBranchOnStatus:
    def test_previous_failed_routes_to_repair(self):
        wf = WORKFLOW("w", on_error="skip")
        wf.step(_Named("bad", ok=False), ok="auto")
        wf.branch(None, {"failed": step_set_flag, "ok": step_increment}, on="previous_failed")
        memory = wf(MEMORY())
        assert memory.get_var("flag") is True
        assert memory.get_var("counter") is None

    def test_previous_status_uses_default(self):
        wf = WORKFLOW("w")
        wf.step(step_increment, name="inc")
        wf.branch(None, {"default": step_set_flag}, on="previous_status")
        assert wf(MEMORY()).get_var("flag") is True

    def test_branch_requires_router_or_on(self):
        import pytest

        with pytest.raises(ValueError):
            WORKFLOW("w").branch(None, {})


class TestWhileLoop:
    def test_runs_until_condition_false(self):
        wf = WORKFLOW("w")
        wf.while_(lambda m: (m.get_var("counter") or 0) < 3, step_increment, name="loop")
        memory = wf(MEMORY())
        assert memory.get_var("counter") == 3
        assert wf.execution_log[0]["iterations"] == 3
        assert wf.execution_log[0]["stopped"] == "condition_false"

    def test_max_iterations_caps_runaway(self):
        wf = WORKFLOW("w")
        wf.while_(lambda m: True, step_increment, name="loop", max_iterations=4)
        memory = wf(MEMORY())
        assert memory.get_var("counter") == 4
        assert wf.execution_log[0]["stopped"] == "max_iterations"

    def test_stops_when_state_repeats(self):
        wf = WORKFLOW("w")
        wf.while_(lambda m: True, lambda m: m, name="loop", state_key="counter", max_iterations=9)
        wf(MEMORY())
        assert wf.execution_log[0]["stopped"] == "stopped_repeated"
        assert wf.execution_log[0]["iterations"] == 1


class _ApprovalStep:
    """Suspends the memory the first time, finishes when given a decision."""

    name = "gate"

    def __init__(self):
        self.runs = 0

    def __call__(self, memory, decision=None):
        self.runs += 1
        if memory.is_suspended() and decision is not None:
            memory.resolve_suspension(decision)
            memory.set_var("approved", decision["approve"])
        elif not memory.is_suspended():
            memory.suspend("approval_required", pending={"what": "refund"})
        return memory


class TestWorkflowSuspendResume:
    def test_log_persisted_on_memory(self):
        wf = WORKFLOW("w")
        wf.step(step_increment, name="inc")
        memory = wf(MEMORY())
        assert memory.get_var("w_log")[0]["step"] == "inc"
        assert memory.get_var("w_cursor") is None

    def test_suspends_then_resumes_after_rehydrate_with_log_preserved(self):
        gate = _ApprovalStep()
        wf = WORKFLOW("w")
        wf.step(step_increment, name="before")
        wf.step(gate, name="gate")
        wf.step(step_set_flag, name="after")

        memory = wf(MEMORY())
        assert [e["status"] for e in wf.execution_log] == ["completed", "suspended"]
        assert memory.get_var("w_cursor") == 1
        assert memory.get_var("flag") is None

        restored = MEMORY.from_json(memory.to_json())
        wf2 = WORKFLOW("w")
        wf2.step(step_increment, name="before")
        wf2.step(gate, name="gate")
        wf2.step(step_set_flag, name="after")

        waiting = wf2(restored)
        assert waiting.is_suspended() and gate.runs == 1  # no decision: nothing re-ran

        done = wf2(restored, decision={"approve": True})
        assert done.get_var("approved") is True and done.get_var("flag") is True
        assert not done.is_suspended()
        statuses = [e["status"] for e in wf2.execution_log]
        assert statuses == ["completed", "suspended", "completed", "completed"]
        assert wf2.execution_log[2]["resumed"] is True
        assert done.get_var("w_cursor") is None

    def test_plain_step_resolved_by_workflow(self):
        def ask(memory):
            if not memory.is_suspended() and not memory.get_var("asked"):
                memory.set_var("asked", True)
                memory.suspend("wait")
            return memory

        wf = WORKFLOW("w")
        wf.step(ask, name="ask")
        wf.step(step_set_flag, name="after")
        memory = wf(MEMORY())
        assert memory.is_suspended()
        memory = wf(memory, decision={"ok": 1})
        assert memory.get_var("flag") is True
        assert not memory.is_suspended()


class TestWorkflowWithGovernedAgent:
    def test_agent_approval_suspends_workflow_and_resumes(self):
        from thoughtflow import AGENT, TOOL

        class Script:
            def __init__(self):
                self.n = 0

            def chat(self, messages, tools=None, params=None, stream=False, cancel=None):
                self.n += 1
                if self.n == 1:
                    return {"content": "", "finish_reason": "tool_calls", "usage": None,
                            "tool_calls": [{"id": "c1", "name": "pay", "arguments": {"amount": 900},
                                            "raw_arguments": "{}", "arguments_error": None}]}
                return {"content": "paid", "tool_calls": [], "finish_reason": "stop", "usage": None}

        paid = []
        tool = TOOL("pay", "Pay", {"amount": {"type": "number"}}, lambda amount: paid.append(amount) or "ok")
        llm = Script()
        policy = {"pay": "approve"}

        def build():
            wf = WORKFLOW("flow")
            wf.step(AGENT(llm=llm, tools=[tool], policy=policy, name="payer"), name="payer", ok="auto")
            wf.step(step_set_flag, name="after")
            return wf

        memory = MEMORY()
        memory.add_msg("user", "Pay 900")
        memory = build()(memory)
        assert memory.is_suspended() and paid == []

        restored = MEMORY.from_json(memory.to_json())
        restored = build()(restored, decision={"approve": True})
        assert paid == [900]
        assert restored.get_var("flag") is True
        assert restored.get_var("payer_status") == "final"

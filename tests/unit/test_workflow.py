"""
Unit tests for the ThoughtFlow WORKFLOW class.

WORKFLOW provides lightweight step-based orchestration with conditional
branching, error handling, and execution tracking.
"""

from __future__ import annotations

import pytest

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

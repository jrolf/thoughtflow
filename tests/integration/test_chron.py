"""
Integration tests for the ThoughtFlow CHRON primitive.

These tests exercise real scheduling with actual time delays. They verify
that the background scheduler thread runs, that interval-based jobs fire
at the correct time, and that state persistence works end-to-end.

Skipped by default unless THOUGHTFLOW_INTEGRATION_TESTS=1 is set, since
they involve real sleeps.
"""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from thoughtflow.chron import CHRON
from thoughtflow import MEMORY


pytestmark = pytest.mark.skipif(
    not os.environ.get("THOUGHTFLOW_INTEGRATION_TESTS"),
    reason="Set THOUGHTFLOW_INTEGRATION_TESTS=1 to run integration tests",
)


class TestChronBackgroundScheduler:
    """Integration tests for the background scheduler loop."""

    def test_start_stop_lifecycle(self):
        """
        start() must launch a background thread that ticks, and stop()
        must cleanly shut it down.
        """
        executed = []

        chron = CHRON()
        chron.add("fast_job", every=1, action=lambda m: executed.append(time.time()))

        # Force next_run to now so the first tick fires immediately
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("UTC"))
        chron._state["fast_job"]["next_run"] = now.isoformat()

        chron.start(tick_interval=1)
        assert chron.running

        # Wait enough for at least 2 executions
        time.sleep(3.5)
        chron.stop()

        assert not chron.running
        assert len(executed) >= 2, "Expected at least 2 executions, got {}".format(
            len(executed)
        )

    def test_background_thread_does_not_block(self):
        """start() must return immediately without blocking the caller."""
        chron = CHRON()
        chron.add("x", every=3600, action=lambda m: None)

        start = time.time()
        chron.start(tick_interval=60)
        elapsed = time.time() - start

        # start() should return in well under 1 second
        assert elapsed < 1.0
        chron.stop()


class TestChronIntervalTiming:
    """Integration tests for interval-based scheduling accuracy."""

    def test_interval_job_fires_at_correct_times(self):
        """
        An interval job should fire approximately every N seconds when
        tick() is called frequently enough.
        """
        timestamps = []

        chron = CHRON()
        chron.add("timed", every=2, action=lambda m: timestamps.append(time.time()))

        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("UTC"))
        chron._state["timed"]["next_run"] = now.isoformat()

        chron.start(tick_interval=1)
        time.sleep(5.5)
        chron.stop()

        # Should have fired at ~0s, ~2s, ~4s = 3 times
        assert len(timestamps) >= 2
        if len(timestamps) >= 2:
            gap = timestamps[1] - timestamps[0]
            assert 1.5 < gap < 3.5, "Gap between executions was {}s".format(gap)


class TestChronStatePersistenceEndToEnd:
    """End-to-end test for state persistence across instances."""

    def test_state_survives_restart(self):
        """
        State written by one CHRON instance must be readable by a new
        instance using the same state file.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            # First instance: add job and fire it twice
            c1 = CHRON(state_file=path)
            c1.add("counter", every=60, action=lambda m: None)
            c1.fire("counter")
            c1.fire("counter")

            assert c1.get("counter")["run_count"] == 2

            # Second instance: load state from file
            c2 = CHRON(state_file=path)
            loaded = c2._state.get("counter", {})
            assert loaded.get("run_count") == 2
            assert loaded.get("last_run") is not None

            # Verify the file is valid JSON
            with open(path) as f:
                data = json.load(f)
            assert "counter" in data
            assert data["counter"]["run_count"] == 2
        finally:
            os.unlink(path)


class TestChronWithThoughtFlowPrimitives:
    """Integration tests showing CHRON working with other primitives."""

    def test_chron_with_action_primitive(self):
        """CHRON must work with ACTION subclasses like SAY."""
        from thoughtflow.actions import NOOP

        noop = NOOP(reason="Scheduled no-op")

        chron = CHRON()
        chron.add("noop_job", every=1, action=noop)

        result = chron.fire("noop_job")
        assert result["status"] == "ok"
        assert chron.get("noop_job")["run_count"] == 1

    def test_chron_with_shared_memory(self):
        """
        CHRON must correctly pass a shared MEMORY across multiple
        executions of the same job.
        """
        shared = MEMORY()

        def accumulate(m):
            count = m.get_var("tick_count") or 0
            m.set_var("tick_count", count + 1)

        chron = CHRON()
        chron.add("accum", every=60, action=accumulate, memory=shared)

        chron.fire("accum")
        chron.fire("accum")
        chron.fire("accum")

        assert shared.get_var("tick_count") == 3

    def test_chron_with_workflow(self):
        """CHRON must work with WORKFLOW as the action."""
        from thoughtflow.workflow import WORKFLOW

        results = []

        def step_a(m):
            m.set_var("step_a", True)
            return m

        def step_b(m):
            results.append(m.get_var("step_a"))
            return m

        wf = WORKFLOW(name="scheduled_flow")
        wf.step(step_a, name="a")
        wf.step(step_b, name="b")

        chron = CHRON()
        chron.add("flow_job", every=60, action=wf)

        chron.fire("flow_job")

        assert results == [True]

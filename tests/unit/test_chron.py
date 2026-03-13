"""
Unit tests for the ThoughtFlow CHRON primitive and its cron expression parser.

CHRON provides schedule management for recurring jobs with both cron
expression and interval-based scheduling, CRUD operations, tick/loop
execution, and optional state persistence.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from thoughtflow._cron_expr import (
    parse_field,
    parse_cron,
    cron_matches,
    next_cron_match,
)
from thoughtflow.chron import CHRON
from thoughtflow import MEMORY


# ============================================================================
# Cron Expression Parser: parse_field
# ============================================================================


class TestParseField:
    """Tests for individual cron field parsing."""

    def test_wildcard(self):
        """Wildcard (*) must return all values in the range."""
        result = parse_field("*", 0, 59)
        assert result == frozenset(range(0, 60))

    def test_exact_value(self):
        """An exact integer must return a single-element set."""
        result = parse_field("30", 0, 59)
        assert result == frozenset({30})

    def test_range(self):
        """A range (1-5) must return all values inclusive."""
        result = parse_field("1-5", 0, 6)
        assert result == frozenset({1, 2, 3, 4, 5})

    def test_step(self):
        """A step (*/15) must return values at the step interval from the range start."""
        result = parse_field("*/15", 0, 59)
        assert result == frozenset({0, 15, 30, 45})

    def test_range_with_step(self):
        """A range with step (1-10/3) must step through the range."""
        result = parse_field("1-10/3", 0, 59)
        assert result == frozenset({1, 4, 7, 10})

    def test_comma_list(self):
        """A comma-separated list must return all listed values."""
        result = parse_field("1,15,30", 0, 59)
        assert result == frozenset({1, 15, 30})

    def test_mixed_list(self):
        """A list can mix exact values, ranges, and steps."""
        result = parse_field("1,5-7,*/30", 0, 59)
        assert 1 in result
        assert 5 in result
        assert 6 in result
        assert 7 in result
        assert 0 in result
        assert 30 in result

    def test_weekday_7_as_sunday(self):
        """Value 7 in a 0-6 weekday field must be treated as Sunday (0)."""
        result = parse_field("7", 0, 6)
        assert result == frozenset({0})

    def test_out_of_range_raises(self):
        """Out-of-range values must raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            parse_field("60", 0, 59)

    def test_zero_step_raises(self):
        """A zero step must raise ValueError."""
        with pytest.raises(ValueError, match="positive"):
            parse_field("*/0", 0, 59)


# ============================================================================
# Cron Expression Parser: parse_cron
# ============================================================================


class TestParseCron:
    """Tests for full 5-field cron expression parsing."""

    def test_every_minute(self):
        """'* * * * *' must allow all values in all fields."""
        fields = parse_cron("* * * * *")
        assert fields["minute"] == frozenset(range(0, 60))
        assert fields["hour"] == frozenset(range(0, 24))
        assert fields["day"] == frozenset(range(1, 32))
        assert fields["month"] == frozenset(range(1, 13))
        assert fields["weekday"] == frozenset(range(0, 7))

    def test_nine_am_daily(self):
        """'0 9 * * *' must only allow minute=0 and hour=9."""
        fields = parse_cron("0 9 * * *")
        assert fields["minute"] == frozenset({0})
        assert fields["hour"] == frozenset({9})
        assert not fields["day_restricted"]
        assert not fields["weekday_restricted"]

    def test_weekdays_only(self):
        """'0 9 * * 1-5' must restrict weekday to Monday-Friday (cron 1-5)."""
        fields = parse_cron("0 9 * * 1-5")
        assert fields["weekday"] == frozenset({1, 2, 3, 4, 5})
        assert fields["weekday_restricted"]

    def test_day_restricted_flag(self):
        """day_restricted must be True when day field is not '*'."""
        fields = parse_cron("0 0 1,15 * *")
        assert fields["day_restricted"]
        assert fields["day"] == frozenset({1, 15})

    def test_wrong_field_count_raises(self):
        """Expressions with != 5 fields must raise ValueError."""
        with pytest.raises(ValueError, match="5 fields"):
            parse_cron("0 9 * *")

        with pytest.raises(ValueError, match="5 fields"):
            parse_cron("0 9 * * * *")


# ============================================================================
# Cron Expression Parser: cron_matches
# ============================================================================


class TestCronMatches:
    """Tests for checking if a datetime matches a cron expression."""

    def test_exact_match(self):
        """A datetime matching all fields must return True."""
        fields = parse_cron("30 9 * * *")
        dt = datetime(2026, 3, 16, 9, 30)  # Monday
        assert cron_matches(fields, dt)

    def test_minute_mismatch(self):
        """Wrong minute must not match."""
        fields = parse_cron("30 9 * * *")
        dt = datetime(2026, 3, 16, 9, 31)
        assert not cron_matches(fields, dt)

    def test_hour_mismatch(self):
        """Wrong hour must not match."""
        fields = parse_cron("30 9 * * *")
        dt = datetime(2026, 3, 16, 10, 30)
        assert not cron_matches(fields, dt)

    def test_weekday_match_monday(self):
        """Monday (Python weekday 0 = cron weekday 1) must match cron '1'."""
        fields = parse_cron("0 0 * * 1")
        monday = datetime(2026, 3, 16, 0, 0)  # March 16, 2026 is a Monday
        assert cron_matches(fields, monday)

    def test_weekday_mismatch(self):
        """A day not in the weekday set must not match."""
        fields = parse_cron("0 0 * * 1")  # Mondays only
        tuesday = datetime(2026, 3, 17, 0, 0)
        assert not cron_matches(fields, tuesday)

    def test_sunday_as_zero(self):
        """Sunday (Python weekday 6 = cron weekday 0) must match cron '0'."""
        fields = parse_cron("0 0 * * 0")
        sunday = datetime(2026, 3, 15, 0, 0)  # March 15, 2026 is a Sunday
        assert cron_matches(fields, sunday)

    def test_or_logic_both_day_fields_restricted(self):
        """
        When both day-of-month and day-of-week are restricted, cron uses
        OR logic: the date matches if EITHER field is satisfied.
        """
        # "15th of month OR Mondays"
        fields = parse_cron("0 0 15 * 1")

        # The 15th (not a Monday) should match via day-of-month
        march_15 = datetime(2026, 3, 15, 0, 0)  # Sunday
        assert cron_matches(fields, march_15)

        # A Monday (not the 15th) should match via day-of-week
        march_16 = datetime(2026, 3, 16, 0, 0)  # Monday
        assert cron_matches(fields, march_16)

        # Neither the 15th nor Monday should NOT match
        march_17 = datetime(2026, 3, 17, 0, 0)  # Tuesday, 17th
        assert not cron_matches(fields, march_17)


# ============================================================================
# Cron Expression Parser: next_cron_match
# ============================================================================


class TestNextCronMatch:
    """Tests for finding the next matching datetime."""

    def test_next_minute(self):
        """next_cron_match must return the very next matching minute."""
        fields = parse_cron("*/5 * * * *")
        after = datetime(2026, 3, 13, 10, 3)
        result = next_cron_match(fields, after)
        assert result == datetime(2026, 3, 13, 10, 5)

    def test_next_hour(self):
        """When no minutes match in the current hour, skip to next hour."""
        fields = parse_cron("0 * * * *")
        after = datetime(2026, 3, 13, 10, 30)
        result = next_cron_match(fields, after)
        assert result == datetime(2026, 3, 13, 11, 0)

    def test_next_day(self):
        """When no hours match today, skip to tomorrow."""
        fields = parse_cron("0 9 * * *")
        after = datetime(2026, 3, 13, 10, 0)
        result = next_cron_match(fields, after)
        assert result == datetime(2026, 3, 14, 9, 0)

    def test_next_month(self):
        """When no days match this month, skip to next matching month."""
        fields = parse_cron("0 0 1 6 *")  # June 1st only
        after = datetime(2026, 3, 13, 0, 0)
        result = next_cron_match(fields, after)
        assert result == datetime(2026, 6, 1, 0, 0)

    def test_strictly_after(self):
        """The result must be strictly after the 'after' time, not equal."""
        fields = parse_cron("30 9 * * *")
        after = datetime(2026, 3, 13, 9, 30)
        result = next_cron_match(fields, after)
        # Should be the NEXT day, not today
        assert result == datetime(2026, 3, 14, 9, 30)

    def test_every_15_minutes(self):
        """*/15 should find the next 15-minute boundary."""
        fields = parse_cron("*/15 * * * *")
        after = datetime(2026, 3, 13, 10, 16)
        result = next_cron_match(fields, after)
        assert result == datetime(2026, 3, 13, 10, 30)

    def test_weekday_skip(self):
        """When restricted to certain weekdays, skip non-matching days."""
        fields = parse_cron("0 9 * * 1")  # Mondays only
        # Friday March 13, 2026
        after = datetime(2026, 3, 13, 10, 0)
        result = next_cron_match(fields, after)
        # Next Monday is March 16
        assert result == datetime(2026, 3, 16, 9, 0)


# ============================================================================
# CHRON: Initialization
# ============================================================================


class TestChronInit:
    """Tests for CHRON initialization."""

    def test_default_name(self):
        """CHRON must default to name='chron'."""
        chron = CHRON()
        assert chron.name == "chron"

    def test_custom_name(self):
        """CHRON must store a custom name."""
        chron = CHRON(name="ops")
        assert chron.name == "ops"

    def test_generates_unique_id(self):
        """Each CHRON instance must have a unique ID."""
        a = CHRON(name="a")
        b = CHRON(name="b")
        assert a.id != b.id

    def test_starts_with_no_jobs(self):
        """A fresh CHRON must have zero jobs."""
        chron = CHRON()
        assert chron.jobs == 0

    def test_default_timezone_utc(self):
        """Without a timezone argument, CHRON must default to UTC."""
        chron = CHRON()
        assert str(chron._tz) == "UTC"

    def test_custom_timezone(self):
        """CHRON must accept a timezone string."""
        chron = CHRON(timezone="America/New_York")
        assert str(chron._tz) == "America/New_York"


# ============================================================================
# CHRON: Add / Get / List
# ============================================================================


class TestChronAdd:
    """Tests for adding jobs."""

    def test_add_cron_job(self):
        """add() with a cron schedule must register the job."""
        chron = CHRON()
        chron.add("daily", schedule="0 9 * * *", action=lambda m: None)

        assert chron.jobs == 1
        info = chron.get("daily")
        assert info["schedule"] == "0 9 * * *"
        assert info["every"] is None
        assert info["enabled"] is True

    def test_add_interval_job(self):
        """add() with an interval must register the job."""
        chron = CHRON()
        chron.add("poll", every=120, action=lambda m: None)

        info = chron.get("poll")
        assert info["every"] == 120
        assert info["schedule"] is None

    def test_add_returns_self(self):
        """add() must return self for method chaining."""
        chron = CHRON()
        result = chron.add("a", every=60, action=lambda m: None)
        assert result is chron

    def test_add_sets_next_run(self):
        """add() must compute an initial next_run."""
        chron = CHRON()
        chron.add("poll", every=60, action=lambda m: None)
        info = chron.get("poll")
        assert info["next_run"] is not None

    def test_add_duplicate_name_raises(self):
        """Adding a job with the same name must raise ValueError."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        with pytest.raises(ValueError, match="already exists"):
            chron.add("x", every=60, action=lambda m: None)

    def test_add_no_schedule_or_interval_raises(self):
        """Providing neither schedule nor every must raise ValueError."""
        chron = CHRON()
        with pytest.raises(ValueError, match="schedule.*every"):
            chron.add("x", action=lambda m: None)

    def test_add_both_schedule_and_interval_raises(self):
        """Providing both schedule and every must raise ValueError."""
        chron = CHRON()
        with pytest.raises(ValueError, match="not both"):
            chron.add("x", schedule="* * * * *", every=60, action=lambda m: None)

    def test_add_no_action_raises(self):
        """Missing action must raise ValueError."""
        chron = CHRON()
        with pytest.raises(ValueError, match="callable"):
            chron.add("x", every=60)

    def test_list_returns_all_jobs(self):
        """list() must return info for every registered job."""
        chron = CHRON()
        chron.add("a", every=60, action=lambda m: None)
        chron.add("b", every=120, action=lambda m: None)

        jobs = chron.list()
        names = [j["name"] for j in jobs]
        assert "a" in names
        assert "b" in names

    def test_get_nonexistent_raises(self):
        """get() with an unknown name must raise KeyError."""
        chron = CHRON()
        with pytest.raises(KeyError):
            chron.get("ghost")


# ============================================================================
# CHRON: Edit / Remove / Pause / Resume
# ============================================================================


class TestChronCrud:
    """Tests for editing, removing, pausing, and resuming jobs."""

    def test_edit_interval(self):
        """edit() must update the interval and recompute next_run."""
        chron = CHRON()
        chron.add("poll", every=60, action=lambda m: None)
        old_next = chron.get("poll")["next_run"]

        chron.edit("poll", every=300)

        info = chron.get("poll")
        assert info["every"] == 300
        assert info["next_run"] != old_next

    def test_edit_schedule_to_cron(self):
        """edit() can change an interval job to a cron job."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.edit("x", schedule="0 9 * * *")

        info = chron.get("x")
        assert info["schedule"] == "0 9 * * *"
        assert info["every"] is None

    def test_edit_nonexistent_raises(self):
        """edit() with an unknown name must raise KeyError."""
        chron = CHRON()
        with pytest.raises(KeyError):
            chron.edit("ghost", every=60)

    def test_remove(self):
        """remove() must delete the job completely."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.remove("x")

        assert chron.jobs == 0
        with pytest.raises(KeyError):
            chron.get("x")

    def test_remove_nonexistent_raises(self):
        """remove() with an unknown name must raise KeyError."""
        chron = CHRON()
        with pytest.raises(KeyError):
            chron.remove("ghost")

    def test_pause(self):
        """pause() must set enabled=False."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.pause("x")

        assert chron.get("x")["enabled"] is False

    def test_resume(self):
        """resume() must set enabled=True and recompute next_run."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.pause("x")
        chron.resume("x")

        info = chron.get("x")
        assert info["enabled"] is True
        assert info["next_run"] is not None

    def test_pause_nonexistent_raises(self):
        """pause() with an unknown name must raise KeyError."""
        chron = CHRON()
        with pytest.raises(KeyError):
            chron.pause("ghost")


# ============================================================================
# CHRON: Tick execution
# ============================================================================


class TestChronTick:
    """Tests for tick-based execution."""

    def test_tick_runs_due_interval_job(self):
        """tick() must execute an interval job when next_run has passed."""
        executed = []
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: executed.append(True))

        # Force next_run to the past
        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()

        results = chron.tick()

        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert len(executed) == 1

    def test_tick_skips_not_due_job(self):
        """tick() must not execute a job whose next_run is in the future."""
        executed = []
        chron = CHRON()
        chron.add("x", every=3600, action=lambda m: executed.append(True))

        # next_run is in the future (set by add)
        results = chron.tick()

        assert len(results) == 0
        assert len(executed) == 0

    def test_tick_skips_paused_job(self):
        """tick() must not execute a paused job even if it is due."""
        executed = []
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: executed.append(True))
        chron.pause("x")

        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()

        results = chron.tick()

        assert len(results) == 0
        assert len(executed) == 0

    def test_tick_updates_state(self):
        """After tick(), run_count and last_run must be updated."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)

        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()

        chron.tick()

        info = chron.get("x")
        assert info["run_count"] == 1
        assert info["last_run"] is not None

    def test_tick_advances_next_run(self):
        """After tick(), next_run must be advanced to a future time."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)

        now = datetime.now(ZoneInfo("UTC"))
        past = now - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()

        chron.tick()

        next_run_str = chron.get("x")["next_run"]
        next_run = datetime.fromisoformat(next_run_str)
        assert next_run > now

    def test_tick_captures_errors(self):
        """tick() must capture exceptions and set status='error'."""
        def failing_action(m):
            raise RuntimeError("boom")

        chron = CHRON()
        chron.add("x", every=60, action=failing_action)

        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()

        results = chron.tick()

        assert results[0]["status"] == "error"
        assert "boom" in results[0]["error"]
        assert chron.get("x")["last_error"] == "boom"

    def test_tick_with_cron_schedule(self):
        """tick() must correctly evaluate cron-based jobs."""
        executed = []
        chron = CHRON()
        chron.add(
            "cron_job",
            schedule="0 9 * * *",
            action=lambda m: executed.append(True),
        )

        # Force next_run to the past
        past = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
        chron._state["cron_job"]["next_run"] = past.isoformat()

        results = chron.tick()
        assert len(results) == 1
        assert len(executed) == 1

    def test_tick_creates_fresh_memory_by_default(self):
        """Each tick execution must get a fresh MEMORY unless configured."""
        memories = []

        def capture_memory(m):
            memories.append(m)

        chron = CHRON()
        chron.add("x", every=60, action=capture_memory)

        # Fire twice
        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        assert len(memories) == 2
        # Each execution gets a different MEMORY instance
        assert memories[0] is not memories[1]

    def test_tick_uses_shared_memory(self):
        """When memory= is provided, all executions share the same instance."""
        shared = MEMORY()

        def set_flag(m):
            count = m.get_var("count") or 0
            m.set_var("count", count + 1)

        chron = CHRON()
        chron.add("x", every=60, action=set_flag, memory=shared)

        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        assert shared.get_var("count") == 2

    def test_tick_uses_memory_factory(self):
        """When memory_factory= is provided, it is called for each execution."""
        call_count = [0]

        def factory():
            call_count[0] += 1
            return MEMORY()

        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None, memory_factory=factory)

        past = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        chron._state["x"]["next_run"] = past.isoformat()
        chron.tick()

        assert call_count[0] == 2


# ============================================================================
# CHRON: Fire (manual trigger)
# ============================================================================


class TestChronFire:
    """Tests for manual job triggering."""

    def test_fire_executes_immediately(self):
        """fire() must execute the job regardless of schedule."""
        executed = []
        chron = CHRON()
        chron.add("x", every=3600, action=lambda m: executed.append(True))

        result = chron.fire("x")

        assert result["status"] == "ok"
        assert len(executed) == 1

    def test_fire_updates_state(self):
        """fire() must update run_count and last_run."""
        chron = CHRON()
        chron.add("x", every=3600, action=lambda m: None)

        chron.fire("x")

        info = chron.get("x")
        assert info["run_count"] == 1
        assert info["last_run"] is not None

    def test_fire_with_override_memory(self):
        """fire() must use the provided memory instead of creating a new one."""
        received = []

        def capture(m):
            received.append(m)

        chron = CHRON()
        chron.add("x", every=3600, action=capture)

        custom_memory = MEMORY()
        custom_memory.set_var("marker", True)
        chron.fire("x", memory=custom_memory)

        assert received[0] is custom_memory
        assert received[0].get_var("marker") is True

    def test_fire_nonexistent_raises(self):
        """fire() with an unknown name must raise KeyError."""
        chron = CHRON()
        with pytest.raises(KeyError):
            chron.fire("ghost")


# ============================================================================
# CHRON: Catch-up logic
# ============================================================================


class TestChronCatchUp:
    """Tests for the catch_up parameter."""

    def test_no_catch_up_skips_to_future(self):
        """
        With catch_up=False (default), after executing a due job,
        next_run must be computed from 'now', skipping over missed runs.
        """
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None, catch_up=False)

        now = datetime.now(ZoneInfo("UTC"))
        # Job was supposed to run 10 minutes ago
        past = now - timedelta(minutes=10)
        chron._state["x"]["next_run"] = past.isoformat()

        chron.tick(now=now)

        # next_run should be ~60 seconds from now, not from the old next_run
        next_run = datetime.fromisoformat(chron.get("x")["next_run"])
        expected_min = now + timedelta(seconds=55)
        assert next_run > expected_min

    def test_catch_up_computes_from_previous_next_run(self):
        """
        With catch_up=True, after executing a due job, next_run must
        be computed from the previous next_run so missed runs are
        replayed one at a time.
        """
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None, catch_up=True)

        now = datetime.now(ZoneInfo("UTC"))
        # Job was supposed to run 3 minutes ago
        old_next_run = now - timedelta(minutes=3)
        chron._state["x"]["next_run"] = old_next_run.isoformat()

        chron.tick(now=now)

        # next_run should be old_next_run + 60s, which is still in the past
        next_run = datetime.fromisoformat(chron.get("x")["next_run"])
        expected = old_next_run + timedelta(seconds=60)
        diff = abs((next_run - expected).total_seconds())
        assert diff < 2  # within 2 seconds tolerance


# ============================================================================
# CHRON: State persistence
# ============================================================================


class TestChronStatePersistence:
    """Tests for JSON state file persistence."""

    def test_save_and_load_state(self):
        """State must survive save and load via a file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_path = f.name

        try:
            # Create scheduler, add a job, fire it
            chron1 = CHRON(state_file=state_path)
            chron1.add("x", every=60, action=lambda m: None)
            chron1.fire("x")

            assert chron1.get("x")["run_count"] == 1
            last_run = chron1.get("x")["last_run"]

            # Create a new scheduler from the same state file
            chron2 = CHRON(state_file=state_path)
            # State should be loaded
            assert chron2._state.get("x", {}).get("run_count") == 1
            assert chron2._state.get("x", {}).get("last_run") == last_run
        finally:
            os.unlink(state_path)

    def test_no_state_file_works(self):
        """Without state_file, CHRON must work purely in-memory."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.fire("x")

        assert chron.get("x")["run_count"] == 1

    def test_missing_state_file_ignored(self):
        """A non-existent state file must not cause an error on init."""
        chron = CHRON(state_file="/tmp/nonexistent_chron_state_12345.json")
        assert chron._state == {}


# ============================================================================
# CHRON: Serialization
# ============================================================================


class TestChronSerialization:
    """Tests for to_dict()."""

    def test_to_dict_includes_jobs(self):
        """to_dict() must include all job definitions."""
        chron = CHRON(name="test")
        chron.add("a", every=60, action=lambda m: None)
        chron.add("b", schedule="0 9 * * *", action=lambda m: None)

        d = chron.to_dict()

        assert d["name"] == "test"
        assert "a" in d["jobs"]
        assert "b" in d["jobs"]
        assert d["jobs"]["a"]["every"] == 60
        assert d["jobs"]["b"]["schedule"] == "0 9 * * *"

    def test_to_dict_includes_state(self):
        """to_dict() must include runtime state."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)
        chron.fire("x")

        d = chron.to_dict()
        assert d["state"]["x"]["run_count"] == 1

    def test_to_dict_excludes_callables(self):
        """to_dict() must not include action or memory callables."""
        chron = CHRON()
        chron.add("x", every=60, action=lambda m: None)

        d = chron.to_dict()
        assert "action" not in d["jobs"]["x"]


# ============================================================================
# CHRON: String representations
# ============================================================================


class TestChronRepr:
    """Tests for __repr__ and __str__."""

    def test_repr_shows_counts(self):
        """__repr__ must show total and active job counts."""
        chron = CHRON(name="ops")
        chron.add("a", every=60, action=lambda m: None)
        chron.add("b", every=60, action=lambda m: None, enabled=False)

        r = repr(chron)
        assert "ops" in r
        assert "jobs=2" in r
        assert "active=1" in r

    def test_str_shows_job_details(self):
        """__str__ must include each job's name, status, and schedule."""
        chron = CHRON(name="ops")
        chron.add("heartbeat", every=60, action=lambda m: None)
        chron.add("nightly", schedule="0 2 * * *", action=lambda m: None)

        s = str(chron)
        assert "ops" in s
        assert "heartbeat" in s
        assert "every 60s" in s
        assert "nightly" in s
        assert "cron: 0 2 * * *" in s

    def test_str_empty_scheduler(self):
        """__str__ with no jobs must show a placeholder."""
        chron = CHRON()
        s = str(chron)
        assert "no jobs" in s


# ============================================================================
# CHRON: Background start/stop
# ============================================================================


class TestChronStartStop:
    """Tests for background thread lifecycle."""

    def test_start_sets_running(self):
        """start() must set running=True."""
        chron = CHRON()
        chron.start(tick_interval=60)

        assert chron.running is True
        chron.stop()

    def test_stop_clears_running(self):
        """stop() must set running=False."""
        chron = CHRON()
        chron.start(tick_interval=60)
        chron.stop()

        assert chron.running is False

    def test_stop_without_start_is_safe(self):
        """stop() must not raise when the scheduler was never started."""
        chron = CHRON()
        chron.stop()
        assert chron.running is False

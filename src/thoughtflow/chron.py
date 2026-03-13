"""
CHRON - schedule manager for recurring jobs.

A top-level primitive for defining, executing, editing, and deleting
scheduled tasks. Supports both cron expressions and fixed-interval
schedules, with two execution modes:

1. **Tick mode** (serverless): An external clock calls ``tick()`` periodically.
   CHRON checks which jobs are due and runs them. Ideal for Lambda, Cloud
   Functions, or any environment where the process is ephemeral.

2. **Loop mode** (daemon): ``run()`` or ``start()`` runs a blocking or
   background scheduling loop. CHRON manages its own timing. Ideal for
   long-running processes, dev servers, and background workers.

Job state (last_run, next_run, run_count) can optionally persist to a
JSON file so that restarts and missed-run detection work correctly.

Zero external dependencies — uses only ``threading``, ``json``, ``datetime``,
and ``zoneinfo`` from the standard library.
"""

from __future__ import annotations

import json
import os
import time as time_module
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from thoughtflow._util import event_stamp
from thoughtflow._cron_expr import parse_cron, next_cron_match


class CHRON:
    """
    Schedule manager for recurring jobs.

    CHRON holds a collection of named jobs, each with a schedule (cron
    expression or fixed interval) and an action (any callable that follows
    the ThoughtFlow contract: receives a MEMORY and optionally returns one).

    It provides full CRUD on the schedule, two execution modes (tick and
    loop), manual firing, and optional state persistence.

    Attributes:
        name (str): Identifier for this scheduler instance.
        id (str): Unique instance ID (event stamp).
        running (bool): Whether the scheduler loop is currently active.

    Example:
        >>> from thoughtflow import CHRON, MEMORY
        >>>
        >>> chron = CHRON(name="ops")
        >>> chron.add("heartbeat", every=60, action=lambda m: print("alive"))
        >>> chron.add("nightly", schedule="0 2 * * *", action=run_cleanup)
        >>>
        >>> # Serverless: external cron calls your handler every minute
        >>> results = chron.tick()
        >>>
        >>> # Daemon: run the loop in background
        >>> chron.start(tick_interval=30)
        >>> # ... later ...
        >>> chron.stop()
    """

    def __init__(self, name="chron", state_file=None, timezone=None):
        """
        Initialize a CHRON scheduler.

        Args:
            name: Identifier for this scheduler (default: "chron").
            state_file: Path to a JSON file for persisting job state
                across restarts. If None, state lives in memory only.
            timezone: Default timezone for cron evaluation, as a string
                like "America/New_York". Defaults to UTC.
        """
        self.name = name
        self.id = event_stamp()
        self._tz = ZoneInfo(timezone) if timezone else ZoneInfo("UTC")
        self._state_file = state_file

        self._jobs = {}     # name -> job config dict
        self._state = {}    # name -> runtime state dict
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        if state_file and os.path.exists(state_file):
            self._load_state()

    # ================================================================
    # CRUD operations
    # ================================================================

    def add(self, name, schedule=None, every=None, action=None,
            enabled=True, catch_up=False, memory=None, memory_factory=None):
        """
        Add a job to the scheduler.

        Exactly one of ``schedule`` or ``every`` must be provided. The
        action must be a callable; it will receive a MEMORY instance as
        its first argument on each invocation.

        Args:
            name: Unique name for this job.
            schedule: Cron expression (5 fields: minute hour day month weekday).
            every: Interval in seconds between runs.
            action: Callable to execute. Should accept a MEMORY as its first
                argument (ACTION, THOUGHT, AGENT, WORKFLOW, or a plain function).
            enabled: Whether the job starts active (default: True).
            catch_up: If True, missed runs (due to downtime) are replayed
                one-by-one on subsequent ticks. If False (default), the
                schedule skips ahead to the next future occurrence.
            memory: A shared MEMORY instance to pass on each execution.
                If None, a fresh MEMORY is created per run.
            memory_factory: Callable that returns a new MEMORY for each run.
                Takes precedence over ``memory`` if both are provided.

        Returns:
            CHRON: Self, for method chaining.

        Raises:
            ValueError: If name already exists, both/neither schedule and
                every are provided, or action is not callable.

        Example:
            >>> chron.add("cleanup", schedule="0 3 * * 0", action=my_cleanup)
            >>> chron.add("poll", every=120, action=check_status)
        """
        if name in self._jobs:
            raise ValueError("Job '{}' already exists".format(name))
        if schedule is None and every is None:
            raise ValueError(
                "Provide 'schedule' (cron expression) or 'every' (seconds)"
            )
        if schedule is not None and every is not None:
            raise ValueError("Provide 'schedule' or 'every', not both")
        if action is None or not callable(action):
            raise ValueError("'action' must be a callable")

        parsed = parse_cron(schedule) if schedule else None

        with self._lock:
            self._jobs[name] = {
                "name": name,
                "schedule": schedule,
                "every": every,
                "action": action,
                "enabled": enabled,
                "catch_up": catch_up,
                "memory": memory,
                "memory_factory": memory_factory,
                "parsed_schedule": parsed,
            }

            # Initialize state if not already loaded from file
            if name not in self._state:
                self._state[name] = _empty_state()

            self._update_next_run(name)

        return self

    def edit(self, name, **kwargs):
        """
        Edit a job's configuration.

        Only the provided keyword arguments are changed; all other fields
        keep their current values. Accepts the same keywords as ``add()``
        (except ``name``).

        If ``schedule`` or ``every`` is changed, the job's ``next_run``
        is recomputed from the current time.

        Args:
            name: Job name to edit.
            **kwargs: Fields to update.

        Returns:
            CHRON: Self, for method chaining.

        Raises:
            KeyError: If job does not exist.

        Example:
            >>> chron.edit("poll", every=300)
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        with self._lock:
            job = self._jobs[name]
            schedule_changed = False

            if "schedule" in kwargs:
                new_sched = kwargs["schedule"]
                job["schedule"] = new_sched
                job["every"] = None
                job["parsed_schedule"] = parse_cron(new_sched) if new_sched else None
                schedule_changed = True

            if "every" in kwargs:
                job["every"] = kwargs["every"]
                job["schedule"] = None
                job["parsed_schedule"] = None
                schedule_changed = True

            for key in ("action", "enabled", "catch_up", "memory", "memory_factory"):
                if key in kwargs:
                    job[key] = kwargs[key]

            if schedule_changed:
                self._update_next_run(name)

        return self

    def remove(self, name):
        """
        Remove a job from the scheduler.

        Args:
            name: Job name to remove.

        Returns:
            CHRON: Self, for method chaining.

        Raises:
            KeyError: If job does not exist.
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        with self._lock:
            del self._jobs[name]
            self._state.pop(name, None)

        self._save_state()
        return self

    def pause(self, name):
        """
        Disable a job without removing it.

        A paused job retains its configuration and state but will not be
        executed by ``tick()`` or the scheduler loop.

        Args:
            name: Job name to pause.

        Returns:
            CHRON: Self, for method chaining.

        Raises:
            KeyError: If job does not exist.
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        self._jobs[name]["enabled"] = False
        return self

    def resume(self, name):
        """
        Re-enable a paused job.

        Recomputes the job's ``next_run`` from the current time so it
        does not immediately fire for the period it was paused.

        Args:
            name: Job name to resume.

        Returns:
            CHRON: Self, for method chaining.

        Raises:
            KeyError: If job does not exist.
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        with self._lock:
            self._jobs[name]["enabled"] = True
            self._update_next_run(name)

        return self

    def get(self, name):
        """
        Get a job's full configuration and current state.

        Returns a plain dict with all serializable fields. The callable
        ``action`` is not included.

        Args:
            name: Job name.

        Returns:
            dict: Job info including schedule, enabled, catch_up, last_run,
                next_run, run_count, last_duration_ms, last_error.

        Raises:
            KeyError: If job does not exist.
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        job = self._jobs[name]
        state = self._state.get(name, {})

        return {
            "name": name,
            "schedule": job["schedule"],
            "every": job["every"],
            "enabled": job["enabled"],
            "catch_up": job["catch_up"],
            "last_run": state.get("last_run"),
            "next_run": state.get("next_run"),
            "run_count": state.get("run_count", 0),
            "last_duration_ms": state.get("last_duration_ms"),
            "last_error": state.get("last_error"),
        }

    def list(self):
        """
        List all jobs with their state.

        Returns:
            list of dict: One entry per job (same format as ``get()``),
                ordered by job name.
        """
        return [self.get(name) for name in sorted(self._jobs)]

    # ================================================================
    # Execution
    # ================================================================

    def tick(self, now=None):
        """
        Check which jobs are due and execute them.

        This is the primary execution method for serverless / external-tick
        environments. Call it periodically (e.g., every minute from a Lambda
        handler) and it runs any jobs whose ``next_run`` has passed.

        Jobs are executed sequentially in alphabetical order by name.

        Args:
            now: Override the current time (timezone-aware datetime).
                Defaults to the current time in the scheduler's timezone.

        Returns:
            list of dict: One result per executed job, with keys
                ``name``, ``status`` ("ok" or "error"), ``duration_ms``,
                and ``error`` (None on success).

        Example:
            >>> results = chron.tick()
            >>> for r in results:
            ...     print(r["name"], r["status"])
        """
        if now is None:
            now = datetime.now(self._tz)

        # Find due jobs under the lock (CRUD-safe)
        due_jobs = []
        with self._lock:
            for name in sorted(self._jobs):
                job = self._jobs[name]
                if not job["enabled"]:
                    continue

                state = self._state.get(name, {})
                next_run_str = state.get("next_run")
                if next_run_str is None:
                    continue

                next_run = datetime.fromisoformat(next_run_str)
                if now >= next_run:
                    due_jobs.append(name)

        # Execute due jobs sequentially
        results = []
        for name in due_jobs:
            result = self._execute_job(name, now)
            results.append(result)

        if results:
            self._save_state()

        return results

    def fire(self, name, memory=None):
        """
        Manually trigger a job regardless of its schedule.

        The job's ``run_count`` and ``last_run`` are updated, but
        ``next_run`` is recomputed from the current time (not from the
        manual fire time), so the regular schedule is not disrupted.

        Args:
            name: Job name to fire.
            memory: Optional MEMORY to use for this execution instead
                of the job's configured memory.

        Returns:
            dict: Execution result with keys ``name``, ``status``,
                ``duration_ms``, ``error``.

        Raises:
            KeyError: If job does not exist.
        """
        if name not in self._jobs:
            raise KeyError("Job '{}' does not exist".format(name))

        now = datetime.now(self._tz)
        result = self._execute_job(name, now, override_memory=memory)
        self._save_state()
        return result

    def run(self, tick_interval=60):
        """
        Run the scheduler in a blocking loop.

        Calls ``tick()`` every ``tick_interval`` seconds. Stops when
        ``stop()`` is called from another thread or on KeyboardInterrupt.

        Args:
            tick_interval: Seconds between tick checks (default: 60).
                Lower values give more precise timing at the cost of
                more frequent polling.
        """
        self._running = True
        try:
            while self._running:
                self.tick()
                # Sleep in small increments so stop() is responsive
                waited = 0.0
                while waited < tick_interval and self._running:
                    increment = min(1.0, tick_interval - waited)
                    time_module.sleep(increment)
                    waited += increment
        except KeyboardInterrupt:
            self._running = False

    def start(self, tick_interval=60):
        """
        Start the scheduler in a background daemon thread.

        The thread is marked as a daemon so it does not prevent process
        exit. Use ``stop()`` to cleanly shut it down.

        Args:
            tick_interval: Seconds between tick checks (default: 60).

        Returns:
            CHRON: Self, for method chaining.
        """
        if self._thread and self._thread.is_alive():
            return self

        self._running = True
        self._thread = threading.Thread(
            target=self.run,
            args=(tick_interval,),
            daemon=True,
            name="chron-{}".format(self.name),
        )
        self._thread.start()
        return self

    def stop(self):
        """
        Stop the background scheduler.

        Signals the loop to exit and waits briefly for the thread to
        finish. Safe to call even if the scheduler is not running.

        Returns:
            CHRON: Self, for method chaining.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        return self

    @property
    def running(self):
        """Whether the scheduler loop is currently active."""
        return self._running

    @property
    def jobs(self):
        """Number of registered jobs."""
        return len(self._jobs)

    # ================================================================
    # Internal: job execution
    # ================================================================

    def _execute_job(self, name, now, override_memory=None):
        """
        Execute a single job and update its state.

        Handles memory creation, timing, error capture, and next_run
        recomputation (including catch_up logic).

        Args:
            name: Job name.
            now: Current datetime (timezone-aware).
            override_memory: Optional MEMORY to use instead of defaults.

        Returns:
            dict: {name, status, duration_ms, error}
        """
        job = self._jobs[name]
        state = self._state.setdefault(name, _empty_state())

        # Save previous next_run for catch_up logic
        previous_next_run_str = state.get("next_run")

        # Prepare memory for this execution
        memory = override_memory
        if memory is None:
            if job["memory_factory"]:
                memory = job["memory_factory"]()
            elif job["memory"]:
                memory = job["memory"]
            else:
                from thoughtflow.memory import MEMORY
                memory = MEMORY()

        start = time_module.time()

        try:
            job["action"](memory)
            elapsed_ms = (time_module.time() - start) * 1000

            state["last_run"] = now.isoformat()
            state["run_count"] = state.get("run_count", 0) + 1
            state["last_duration_ms"] = round(elapsed_ms, 2)
            state["last_error"] = None

            self._compute_next_run_after_execution(
                name, now, previous_next_run_str
            )

            return {
                "name": name,
                "status": "ok",
                "duration_ms": round(elapsed_ms, 2),
                "error": None,
            }

        except Exception as e:
            elapsed_ms = (time_module.time() - start) * 1000

            state["last_run"] = now.isoformat()
            state["run_count"] = state.get("run_count", 0) + 1
            state["last_duration_ms"] = round(elapsed_ms, 2)
            state["last_error"] = str(e)

            self._compute_next_run_after_execution(
                name, now, previous_next_run_str
            )

            return {
                "name": name,
                "status": "error",
                "duration_ms": round(elapsed_ms, 2),
                "error": str(e),
            }

    def _compute_next_run_after_execution(self, name, now, previous_next_run_str):
        """
        Decide the base time for next_run computation after a job executes.

        With catch_up=True, the base is the previous next_run so that missed
        runs are replayed one per tick. With catch_up=False, the base is
        ``now`` so the schedule jumps to the next future occurrence.

        Args:
            name: Job name.
            now: Current datetime.
            previous_next_run_str: ISO string of the job's next_run before execution.
        """
        job = self._jobs[name]

        if job["catch_up"] and previous_next_run_str:
            base = datetime.fromisoformat(previous_next_run_str)
        else:
            base = now

        self._update_next_run(name, from_time=base)

    # ================================================================
    # Internal: next_run computation
    # ================================================================

    def _update_next_run(self, name, from_time=None):
        """
        Compute and store the next_run time for a job.

        For cron-based jobs, uses next_cron_match to find the next
        occurrence after ``from_time``. For interval-based jobs, adds
        the interval to ``from_time``.

        Args:
            name: Job name.
            from_time: Base datetime for the computation. Defaults to now.
        """
        job = self._jobs[name]
        state = self._state.setdefault(name, _empty_state())

        base = from_time or datetime.now(self._tz)

        # Ensure base is timezone-aware
        if base.tzinfo is None:
            base = base.replace(tzinfo=self._tz)

        if job["parsed_schedule"]:
            # Cron-based: find next matching time in scheduler's timezone
            local_base = base.astimezone(self._tz)
            naive_base = local_base.replace(tzinfo=None)
            next_dt = next_cron_match(job["parsed_schedule"], naive_base)
            if next_dt:
                aware_next = next_dt.replace(tzinfo=self._tz)
                state["next_run"] = aware_next.isoformat()
            else:
                state["next_run"] = None

        elif job["every"]:
            # Interval-based: simply add the interval
            next_dt = base + timedelta(seconds=job["every"])
            state["next_run"] = next_dt.isoformat()

    # ================================================================
    # State persistence
    # ================================================================

    def _save_state(self):
        """Save job state to the state file if configured. Best-effort."""
        if not self._state_file:
            return

        try:
            parent = os.path.dirname(self._state_file)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception:
            pass

    def _load_state(self):
        """Load job state from the state file."""
        if not self._state_file or not os.path.exists(self._state_file):
            return

        try:
            with open(self._state_file, "r") as f:
                self._state = json.load(f)
        except Exception:
            self._state = {}

    # ================================================================
    # Serialization
    # ================================================================

    def to_dict(self):
        """
        Serialize the scheduler's configuration and state.

        Action callables, memory instances, and memory factories cannot
        be serialized. Only schedule definitions and runtime state are
        included.

        Returns:
            dict: Serializable representation of the scheduler.
        """
        jobs = {}
        for name, job in self._jobs.items():
            jobs[name] = {
                "name": name,
                "schedule": job["schedule"],
                "every": job["every"],
                "enabled": job["enabled"],
                "catch_up": job["catch_up"],
            }

        return {
            "name": self.name,
            "id": self.id,
            "timezone": str(self._tz),
            "jobs": jobs,
            "state": dict(self._state),
        }

    # ================================================================
    # Representations
    # ================================================================

    def __repr__(self):
        """Concise representation showing job counts."""
        total = len(self._jobs)
        active = sum(1 for j in self._jobs.values() if j["enabled"])
        return "CHRON(name='{}', jobs={}, active={})".format(
            self.name, total, active
        )

    def __str__(self):
        """
        Human-readable summary of the scheduler and all its jobs.

        Shows each job's name, status, schedule, run count, and next run.
        """
        lines = ["CHRON '{}':".format(self.name)]

        if not self._jobs:
            lines.append("  (no jobs)")
            return "\n".join(lines)

        for name in sorted(self._jobs):
            job = self._jobs[name]
            status = "enabled" if job["enabled"] else "paused"

            if job["schedule"]:
                timing = "cron: {}".format(job["schedule"])
            else:
                timing = "every {}s".format(job["every"])

            state = self._state.get(name, {})
            run_count = state.get("run_count", 0)
            next_run = state.get("next_run", "—")

            lines.append("  {} [{}] {} (runs: {}, next: {})".format(
                name, status, timing, run_count, next_run
            ))

        return "\n".join(lines)


def _empty_state():
    """Return the default state dict for a new job."""
    return {
        "last_run": None,
        "next_run": None,
        "run_count": 0,
        "last_duration_ms": None,
        "last_error": None,
    }

"""
WORKFLOW class for ThoughtFlow.

WORKFLOW provides lightweight orchestration for non-linear execution flows.
It defines a sequence of steps where each step is a callable (THOUGHT, AGENT,
ACTION, or any function). Steps can include conditional branching, parallel
execution, and early termination.

The WORKFLOW is "Python control flow with guardrails" — it does not introduce
a DSL or graph language. Instead, it provides a thin layer that handles step
sequencing, conditional routing, error recovery, and execution tracking while
keeping the logic visible as plain Python.
"""

from __future__ import annotations

import time as time_module

from thoughtflow._util import event_stamp


class _StepDegraded(Exception):
    """Raised internally when a step's ``ok`` predicate returns False."""


class WORKFLOW:
    """
    Lightweight step-based orchestration for non-linear execution flows.

    A WORKFLOW is a named sequence of steps, where each step is defined by:
    - A callable (THOUGHT, AGENT, ACTION, or any function)
    - An optional condition (a callable that takes memory and returns bool)
    - An optional name for identification and logging

    Steps are executed in order. Steps with conditions are skipped if the
    condition returns False. A step can also be a branch point that routes
    to different sub-steps based on runtime state.

    Preserves the ThoughtFlow contract: memory = workflow(memory).

    Attributes:
        name (str): Identifier for this workflow.
        steps (list): Registered steps with their configuration.
        id (str): Unique identifier for this workflow instance.
        execution_log (list): Record of executed steps with timing.

    Example:
        >>> workflow = WORKFLOW(name="research_flow")
        >>> workflow.step(classify_thought, name="classify")
        >>> workflow.step(search_action, condition=lambda m: m.get_var("needs_search"))
        >>> workflow.step(summarize_thought, name="summarize")
        >>>
        >>> memory = MEMORY()
        >>> memory.add_msg("user", "Tell me about quantum computing")
        >>> memory = workflow(memory)
    """

    def __init__(self, name="workflow", on_error="stop"):
        """
        Initialize a WORKFLOW.

        Args:
            name (str): Identifier for this workflow.
            on_error (str): Error handling strategy. One of:
                - 'stop': Stop the workflow on first error (default).
                - 'skip': Skip the failed step and continue.
                - 'retry': Retry the failed step once before stopping.
        """
        self.name = name
        self.id = event_stamp()
        self.steps = []
        self.on_error = on_error
        self.execution_log = []
        self._step_note = {}

    def step(self, fn, name=None, condition=None, ok=None):
        """
        Add a step to the workflow.

        Steps are executed in the order they are added. Each step is a
        callable that receives memory and returns memory (or transforms it).

        Args:
            fn (callable): The step function. Should accept memory as its
                first argument and return the (possibly modified) memory.
            name (str, optional): Name for identification and logging.
                Defaults to the function's __name__ or a positional label.
            condition (callable, optional): A function(memory) -> bool. If
                provided, the step is only executed when the condition returns
                True. This enables conditional branching.
            ok (callable or "auto", optional): Success predicate checked after
                the step returns. ``ok(memory) -> bool``, or ``"auto"`` to read
                ``{fn.name}_outcome["ok"]`` (THOUGHT and AGENT write it). A
                False result records status ``"degraded"`` and applies
                ``on_error`` exactly like an exception would.

        Returns:
            WORKFLOW: Self, for method chaining.

        Example:
            >>> wf = WORKFLOW("my_flow")
            >>> wf.step(step_a, name="first")
            >>> wf.step(step_b, name="cond", condition=lambda m: m.get_var("flag"))
            >>> wf.step(classify, ok="auto")
        """
        fallback = 'step_{}'.format(len(self.steps))
        default_name = getattr(fn, 'name', getattr(fn, '__name__', fallback))
        step_name = name or default_name
        self.steps.append({
            "fn": fn,
            "name": step_name,
            "condition": condition,
            "ok": self._make_ok(fn, ok),
        })
        return self

    @staticmethod
    def _make_ok(fn, ok):
        """Turn the ``ok`` argument into a ``fn(memory) -> bool`` predicate or None."""
        if ok is None:
            return None
        if callable(ok):
            return ok
        if ok == "auto":
            outcome_key = "{}_outcome".format(getattr(fn, "name", ""))

            def auto_ok(memory):
                outcome = memory.get_var(outcome_key)
                return True if outcome is None else bool(outcome.get("ok", True))

            return auto_ok
        raise ValueError("ok must be None, a callable, or 'auto', got: {!r}".format(ok))

    def branch(self, router_fn, branches, name=None, on=None):
        """
        Add a branch point that routes to different steps based on a key.

        The router_fn examines memory and returns a string key. The
        corresponding callable in the branches dict is then executed.

        Args:
            router_fn (callable): A function(memory) -> str that returns the
                branch key. May be None when ``on`` is given.
            branches (dict): Maps branch keys to callables. Each callable
                receives memory and returns memory. ``"default"`` is the
                fallback key.
            name (str, optional): Name for identification.
            on (str, optional): Route on workflow state instead of ``router_fn``.
                ``"previous_status"`` uses the previous step's log status
                (``completed``, ``degraded``, ``error``, ...); ``"previous_failed"``
                uses ``"failed"`` or ``"ok"``.

        Returns:
            WORKFLOW: Self, for method chaining.

        Example:
            >>> wf.branch(
            ...     router_fn=lambda m: m.get_var("category"),
            ...     branches={
            ...         "technical": handle_technical,
            ...         "creative": handle_creative,
            ...         "default": handle_default,
            ...     },
            ...     name="route_by_category",
            ... )
            >>> wf.branch(None, {"failed": repair, "ok": keep}, on="previous_failed")
        """
        if on not in (None, "previous_status", "previous_failed"):
            raise ValueError("on must be None, 'previous_status', or 'previous_failed'")
        if on is None and router_fn is None:
            raise ValueError("branch needs router_fn or on=")
        step_name = name or "branch_{}".format(len(self.steps))

        def branch_step(memory):
            """Execute the branch selected by the router function."""
            if on is None:
                key = router_fn(memory)
            else:
                previous = self.execution_log[-1]["status"] if self.execution_log else "none"
                if on == "previous_status":
                    key = previous
                else:
                    key = "failed" if previous in self.FAILED_STATUSES else "ok"
            handler = branches.get(key, branches.get("default"))
            if handler:
                return handler(memory)
            return memory

        branch_step.__name__ = step_name

        self.steps.append({
            "fn": branch_step,
            "name": step_name,
            "condition": None,
            "ok": None,
        })
        return self

    def while_(self, condition, body_fn, name=None, max_iterations=10, state_key=None):
        """
        Add a bounded loop step: run ``body_fn`` while ``condition(memory)``.

        The loop always stops after ``max_iterations``. With ``state_key`` it
        also stops early (``stopped_repeated``) when the body leaves that
        variable unchanged, which catches loops that spin without progress.
        The step's log entry records ``iterations`` and ``stopped``.

        Args:
            condition (callable): ``condition(memory) -> bool``.
            body_fn (callable): Step function run each iteration.
            name (str, optional): Step name.
            max_iterations (int): Hard cap (default 10).
            state_key (str, optional): Variable watched for progress.

        Returns:
            WORKFLOW: Self, for method chaining.
        """
        step_name = name or "while_{}".format(len(self.steps))

        progress_key = "{}_loop".format(step_name)

        def while_step(memory, decision=None):
            """Run the body until the condition fails, the cap hits, state repeats, or it suspends."""
            iterations = 0
            stopped = "condition_false"
            progress = memory.get_var(progress_key) or {}
            if progress.get("suspended"):
                # Resuming: keep earlier iterations and hand the decision to the body.
                iterations = int(progress.get("iterations", 0))
            elif decision is not None:
                decision = None
            while condition(memory):
                if iterations >= max_iterations:
                    stopped = "max_iterations"
                    break
                before = repr(memory.get_var(state_key)) if state_key else None
                before_id = self._suspension_id(memory)
                if decision is not None and not self._accepts_decision(body_fn):
                    memory.resolve_suspension(decision)
                    decision = None
                    before_id = None
                if decision is not None:
                    result = body_fn(memory, decision=decision)
                else:
                    result = body_fn(memory)
                decision = None
                if result is not None:
                    memory = result
                after_id = self._suspension_id(memory)
                if after_id is not None and after_id != before_id:
                    memory.set_var(progress_key, {"iterations": iterations, "suspended": True},
                                   desc="Loop progress for step: {}".format(step_name))
                    stopped = "suspended"
                    break
                iterations += 1
                if state_key and repr(memory.get_var(state_key)) == before:
                    stopped = "stopped_repeated"
                    break
            if stopped != "suspended" and progress.get("suspended"):
                memory.set_var(progress_key, {"iterations": iterations, "suspended": False},
                               desc="Loop progress for step: {}".format(step_name))
            self._step_note = {"iterations": iterations, "stopped": stopped}
            return memory

        while_step.__name__ = step_name
        self.steps.append({
            "fn": while_step,
            "name": step_name,
            "condition": None,
            "ok": None,
        })
        return self

    FAILED_STATUSES = ("error", "degraded", "retry_failed")

    def _attempt(self, step_config, memory, decision=None):
        """
        Run one step once. Returns ``(memory, ran)``; ``ran`` is False when skipped.

        Raises ``_StepDegraded`` when the ``ok`` predicate fails, or whatever
        the step or condition raised.
        """
        condition = step_config["condition"]
        if condition is not None and not condition(memory):
            return memory, False
        fn = step_config["fn"]
        if decision is not None and self._accepts_decision(fn):
            result = fn(memory, decision=decision)
        else:
            result = fn(memory)
        if result is not None:
            memory = result
        ok = step_config.get("ok")
        # A step that left the memory suspended is waiting, not failing.
        if ok is not None and self._suspension_id(memory) is None and not ok(memory):
            raise _StepDegraded("step '{}' reported not ok".format(step_config["name"]))
        return memory, True

    @staticmethod
    def _accepts_decision(fn):
        """True when ``fn`` can take a ``decision=`` keyword (AGENT does)."""
        import inspect

        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            return False
        return "decision" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )

    @staticmethod
    def _suspension_id(memory):
        """Id of the current suspension, or None when the memory is not suspended."""
        is_suspended = getattr(memory, "is_suspended", None)
        if not callable(is_suspended) or not is_suspended():
            return None
        return (memory.get_suspension() or {}).get("id")

    def __call__(self, memory, decision=None):
        """
        Execute the workflow by running each step in sequence.

        Steps with conditions are skipped when the condition returns False.
        Error handling follows the on_error strategy. When a step leaves the
        memory suspended (for example an AGENT waiting for approval), the
        workflow records status ``"suspended"``, stores ``{name}_cursor`` and
        ``{name}_log`` on the memory, and returns. Call it again on the
        rehydrated memory with ``decision=...`` to resume at that step with the
        log preserved.

        Args:
            memory: A MEMORY instance.
            decision (dict, optional): Resolution for a suspended workflow.

        Returns:
            MEMORY: The memory after all steps have been executed.
        """
        cursor_key = "{}_cursor".format(self.name)
        log_key = "{}_log".format(self.name)
        start = 0
        resuming = False
        self.execution_log = []
        cursor = memory.get_var(cursor_key) if hasattr(memory, "get_var") else None
        if cursor is not None and self._suspension_id(memory) is not None:
            start = int(cursor)
            resuming = True
            self.execution_log = list(memory.get_var(log_key) or [])
            if decision is None:
                return self._finalize(memory, cursor=start)

        suspended_at = None
        for idx in range(start, len(self.steps)):
            step_config = self.steps[idx]
            step_name = step_config["name"]
            use_decision = decision if (resuming and idx == start) else None
            before_id = self._suspension_id(memory)
            if use_decision is not None and not self._accepts_decision(step_config["fn"]):
                if hasattr(memory, "resolve_suspension"):
                    memory.resolve_suspension(use_decision)
                use_decision = None
                before_id = None

            self._step_note = {}
            start_time = time_module.time()
            try:
                memory, ran = self._attempt(step_config, memory, use_decision)
                if not ran:
                    self.execution_log.append({
                        "step": step_name,
                        "status": "skipped",
                        "reason": "condition_false",
                    })
                    continue
                duration_ms = (time_module.time() - start_time) * 1000
                entry = {
                    "step": step_name,
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                }
                entry.update(self._step_note)
                if resuming and idx == start:
                    entry["resumed"] = True
                self.execution_log.append(entry)
                after_id = self._suspension_id(memory)
                if after_id is not None and after_id != before_id:
                    self.execution_log[-1]["status"] = "suspended"
                    suspended_at = idx
                    break

            except Exception as e:
                duration_ms = (time_module.time() - start_time) * 1000
                status = "degraded" if isinstance(e, _StepDegraded) else "error"
                self.execution_log.append({
                    "step": step_name,
                    "status": status,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                })

                if self.on_error == "stop":
                    if hasattr(memory, "add_log"):
                        memory.add_log("WORKFLOW '{}' stopped at step '{}': {}".format(
                            self.name, step_name, e
                        ))
                    break
                elif self.on_error == "retry":
                    # One retry attempt (re-evaluates condition too if present)
                    try:
                        memory, ran = self._attempt(step_config, memory)
                        if not ran:
                            self.execution_log.append({
                                "step": step_name,
                                "status": "skipped",
                                "reason": "condition_false",
                            })
                            continue
                        elapsed_ms = (time_module.time() - start_time) * 1000
                        duration_retry = round(elapsed_ms, 2)
                        self.execution_log.append({
                            "step": step_name,
                            "status": "completed_on_retry",
                            "duration_ms": duration_retry,
                        })
                    except Exception as retry_e:
                        self.execution_log.append({
                            "step": step_name,
                            "status": "retry_failed",
                            "error": str(retry_e),
                        })
                        if hasattr(memory, "add_log"):
                            memory.add_log("WORKFLOW retry failed at '{}': {}".format(
                                step_name, retry_e
                            ))
                        break
                # on_error == "skip" — just continue to next step

        return self._finalize(memory, cursor=suspended_at)

    def _finalize(self, memory, cursor=None):
        """Persist status, log, and cursor on MEMORY and return it."""
        if hasattr(memory, "set_var"):
            done_statuses = ("completed", "completed_on_retry")
            completed = sum(
                1 for e in self.execution_log if e["status"] in done_statuses
            )
            skipped = sum(1 for e in self.execution_log if e["status"] == "skipped")
            errors = sum(1 for e in self.execution_log if "error" in e["status"])
            degraded = sum(1 for e in self.execution_log if e["status"] == "degraded")
            status = {
                "total_steps": len(self.steps),
                "completed": completed,
                "skipped": skipped,
                "errors": errors,
            }
            if degraded:
                status["degraded"] = degraded
            if cursor is not None:
                status["suspended_at"] = cursor
            memory.set_var(
                "{}_status".format(self.name),
                status,
                desc="Execution status for workflow: {}".format(self.name)
            )
            memory.set_var(
                "{}_log".format(self.name),
                [dict(entry) for entry in self.execution_log],
                desc="Execution log for workflow: {}".format(self.name),
            )
            memory.set_var(
                "{}_cursor".format(self.name),
                cursor,
                desc="Resume cursor for workflow: {}".format(self.name),
            )

        return memory

    def __str__(self):
        """Return a concise string representation."""
        step_names = [s["name"] for s in self.steps]
        return "WORKFLOW({}, steps={})".format(self.name, step_names)

    def __repr__(self):
        """Return a detailed string representation."""
        return "WORKFLOW(name='{}', steps={}, on_error='{}')".format(
            self.name, len(self.steps), self.on_error
        )

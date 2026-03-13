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

    Preserves the Thoughtflow contract: memory = workflow(memory).

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

    def step(self, fn, name=None, condition=None):
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

        Returns:
            WORKFLOW: Self, for method chaining.

        Example:
            >>> wf = WORKFLOW("my_flow")
            >>> wf.step(step_a, name="first")
            >>> wf.step(step_b, name="cond", condition=lambda m: m.get_var("flag"))
        """
        fallback = 'step_{}'.format(len(self.steps))
        default_name = getattr(fn, 'name', getattr(fn, '__name__', fallback))
        step_name = name or default_name
        self.steps.append({
            "fn": fn,
            "name": step_name,
            "condition": condition,
        })
        return self

    def branch(self, router_fn, branches, name=None):
        """
        Add a branch point that routes to different steps based on a key.

        The router_fn examines memory and returns a string key. The
        corresponding callable in the branches dict is then executed.

        Args:
            router_fn (callable): A function(memory) -> str that returns the
                branch key.
            branches (dict): Maps branch keys to callables. Each callable
                receives memory and returns memory.
            name (str, optional): Name for identification.

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
        """
        step_name = name or "branch_{}".format(len(self.steps))

        def branch_step(memory):
            """Execute the branch selected by the router function."""
            key = router_fn(memory)
            handler = branches.get(key, branches.get("default"))
            if handler:
                return handler(memory)
            return memory

        branch_step.__name__ = step_name

        self.steps.append({
            "fn": branch_step,
            "name": step_name,
            "condition": None,
        })
        return self

    def __call__(self, memory):
        """
        Execute the workflow by running each step in sequence.

        Steps with conditions are skipped when the condition returns False.
        Error handling follows the on_error strategy.

        Args:
            memory: A MEMORY instance.

        Returns:
            MEMORY: The memory after all steps have been executed.
        """
        self.execution_log = []

        for step_config in self.steps:
            fn = step_config["fn"]
            step_name = step_config["name"]
            condition = step_config["condition"]

            # Check condition
            if condition is not None:
                try:
                    should_run = condition(memory)
                except Exception:
                    should_run = False

                if not should_run:
                    self.execution_log.append({
                        "step": step_name,
                        "status": "skipped",
                        "reason": "condition_false",
                    })
                    continue

            # Execute the step
            start_time = time_module.time()
            try:
                result = fn(memory)
                # If the step returns memory, use it; otherwise keep the original
                if result is not None:
                    memory = result

                duration_ms = (time_module.time() - start_time) * 1000
                self.execution_log.append({
                    "step": step_name,
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                })

            except Exception as e:
                duration_ms = (time_module.time() - start_time) * 1000
                self.execution_log.append({
                    "step": step_name,
                    "status": "error",
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
                    # One retry attempt
                    try:
                        result = fn(memory)
                        if result is not None:
                            memory = result
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

        # Store workflow result metadata
        if hasattr(memory, "set_var"):
            done_statuses = ("completed", "completed_on_retry")
            completed = sum(
                1 for e in self.execution_log if e["status"] in done_statuses
            )
            skipped = sum(1 for e in self.execution_log if e["status"] == "skipped")
            errors = sum(1 for e in self.execution_log if "error" in e["status"])
            memory.set_var(
                "{}_status".format(self.name),
                {
                    "total_steps": len(self.steps),
                    "completed": completed,
                    "skipped": skipped,
                    "errors": errors,
                },
                desc="Execution status for workflow: {}".format(self.name)
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

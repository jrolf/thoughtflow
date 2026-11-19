"""
PlanActAgent for ThoughtFlow.

The PlanActAgent first generates a plan (a sequence of steps), then executes
each step. If a step fails or conditions change, the agent can replan.
This implements the Plan-then-Execute pattern with adaptive replanning.
"""

from __future__ import annotations

import json
import re

from thoughtflow.agent import AGENT


class PlanActAgent(AGENT):
    """
    Plan-then-execute agent with adaptive replanning.

    PLANACT extends AGENT by splitting execution into two phases:
    1. **Planning:** The LLM generates a structured plan (list of steps)
    2. **Execution:** Each step is executed in order using available tools
    3. **Replanning:** If a step fails or produces unexpected results, the
       agent can generate a new plan for the remaining work

    This is effective for complex, multi-step tasks where the agent needs
    to break down the problem before acting.

    Attributes:
        plan_prompt (str): Prompt template for plan generation.
        replan_on_failure (bool): If True, replan when a step fails.
        current_plan (list): The current plan (list of step dicts).
        execution_log (list): Log of executed steps and their outcomes.

    Example:
        >>> agent = PLANACT(
        ...     llm=llm,
        ...     tools=[search_tool, write_tool],
        ...     system_prompt="You are a research assistant.",
        ... )
        >>> memory = MEMORY()
        >>> memory.add_msg("user", "Research Python frameworks and write a summary.")
        >>> memory = agent(memory)
    """

    DEFAULT_PLAN_PROMPT = (
        "Break down the following task into a numbered list of concrete steps. "
        "For each step, specify which tool to use (if any) and what arguments. "
        "Return ONLY a JSON list of objects, each with 'step', 'tool' (or null), "
        "and 'args' (or {{}}).\n\nTask: {task}\n\n"
        "Available tools: {tool_list}"
    )

    def __init__(self, plan_prompt=None, replan_on_failure=True, max_replans=2, **kwargs):
        """
        Initialize a PlanActAgent.

        Args:
            plan_prompt (str, optional): Prompt template for plan generation.
                Supports ``{task}`` / ``{tool_list}`` (as well as legacy
                ``{{task}}`` / ``{{tool_list}}``) placeholders without mangling
                JSON braces.
            replan_on_failure (bool): Whether to regenerate and execute a new
                plan when a step fails. Defaults to ``True``.
            max_replans (int): Maximum number of replan cycles allowed per call
                (default ``2``).
            **kwargs: All other arguments passed to ``AGENT.__init__``.
        """
        super().__init__(**kwargs)
        self.plan_prompt = plan_prompt or self.DEFAULT_PLAN_PROMPT
        self.replan_on_failure = replan_on_failure
        self.max_replans = max(0, int(max_replans))
        self.current_plan = []
        self.execution_log = []
        self.plan_regex = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

    @staticmethod
    def _is_tool_failure(result):
        """
        Determine whether a tool execution result represents an operational failure.

        Checks structured error dicts (``success is False`` or non-empty ``error``)
        and explicit ``AGENT._execute_tool`` error strings (``"Error executing ..."``
        or ``"Error: ..."``) without misclassifying normal prose that happens to
        begin with the word ``"Error"`` (e.g. ``"Error handling in Python..."``).
        """
        if isinstance(result, dict):
            if result.get("success") is False:
                return True
            if result.get("error"):
                return True
            if result.get("status") in ("error", "timeout"):
                return True
            return False
        if isinstance(result, str):
            stripped = result.strip()
            if stripped.startswith("Error executing ") or stripped.startswith("Error:"):
                return True
        return False

    def __call__(self, memory):
        """
        Run the bounded plan-then-execute-and-replan loop (#24).

        1. Extract the task from the last user message
        2. Generate an initial plan
        3. Execute steps sequentially in an outer loop bounded by ``max_replans``
        4. When a step fails and ``replan_on_failure`` is ``True``, generate a
           replacement plan for remaining work and execute it
        5. Produce a final summary and record ``{name}_result``, ``{name}_status``,
           and ``{name}_outcome``

        Args:
            memory: A MEMORY instance.

        Returns:
            MEMORY: Updated memory with execution results.
        """
        self.execution_log = []

        task = self._extract_task(memory)
        if not task:
            if hasattr(memory, "add_msg"):
                memory.add_msg("assistant", "No task found to plan.")
            return memory

        self.current_plan = self._generate_plan(task)
        if not self.current_plan:
            return super().__call__(memory)

        self.execution_log.append({
            "step": "Plan",
            "tool": None,
            "result": json.dumps(self.current_plan),
            "success": True,
        })

        if hasattr(memory, "add_msg"):
            memory.add_msg("assistant", "Plan:\n" + json.dumps(self.current_plan))

        replans_used = 0
        steps_executed = 0

        while self.current_plan:
            replanned = False
            for step_idx, step in enumerate(self.current_plan):
                if not isinstance(step, dict):
                    step_desc = str(step)
                    tool_name = None
                    tool_args = {}
                else:
                    raw_label = step.get("step")
                    step_desc = (
                        str(raw_label)
                        if raw_label is not None and str(raw_label) != ""
                        else "Step {}".format(step_idx + 1)
                    )
                    tool_name = step.get("tool")
                    tool_args = step.get("args") if isinstance(step.get("args"), dict) else {}

                steps_executed += 1

                if tool_name and tool_name in self._tool_map:
                    result = self._execute_tool(
                        tool_name,
                        tool_args,
                        context={"memory": memory, "agent": self},
                    )
                    success = not self._is_tool_failure(result)

                    self.execution_log.append({
                        "step": step_desc,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": str(result),
                        "success": success,
                    })

                    if hasattr(memory, "add_msg"):
                        memory.add_msg(
                            "assistant",
                            "Step: {}\nResult: {}".format(step_desc, result),
                        )

                    if not success and self.replan_on_failure and replans_used < self.max_replans:
                        replans_used += 1
                        remaining_task = self._summarize_remaining(task)
                        new_plan = self._generate_plan(remaining_task)
                        if new_plan:
                            self.current_plan = new_plan
                            self.execution_log.append({
                                "step": "Replan",
                                "tool": None,
                                "result": json.dumps(self.current_plan),
                                "success": True,
                            })
                            if hasattr(memory, "add_msg"):
                                memory.add_msg(
                                    "assistant",
                                    "Replan:\n" + json.dumps(self.current_plan),
                                )
                            replanned = True
                        break
                elif tool_name and tool_name not in self._tool_map:
                    err_msg = "Error: unknown tool '{}'".format(tool_name)
                    self.execution_log.append({
                        "step": step_desc,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": err_msg,
                        "success": False,
                    })
                    if self.replan_on_failure and replans_used < self.max_replans:
                        replans_used += 1
                        remaining_task = self._summarize_remaining(task)
                        new_plan = self._generate_plan(remaining_task)
                        if new_plan:
                            self.current_plan = new_plan
                            self.execution_log.append({
                                "step": "Replan",
                                "tool": None,
                                "result": json.dumps(self.current_plan),
                                "success": True,
                            })
                            if hasattr(memory, "add_msg"):
                                memory.add_msg(
                                    "assistant",
                                    "Replan:\n" + json.dumps(self.current_plan),
                                )
                            replanned = True
                        break
                else:
                    self.execution_log.append({
                        "step": step_desc,
                        "tool": None,
                        "result": "Reasoning step",
                        "success": True,
                    })

            if not replanned:
                break

        summary = self._generate_summary(memory, task)
        if hasattr(memory, "add_msg"):
            memory.add_msg("assistant", summary)
        if hasattr(memory, "set_var"):
            memory.set_var(
                "{}_result".format(self.name),
                summary,
                desc="Final result from PlanActAgent",
            )
            memory.set_var(
                "{}_status".format(self.name),
                "completed",
                desc="Execution status for PlanActAgent",
            )
            any_unrecovered_failure = any(
                not e["success"] for e in self.execution_log
            ) and not (self.execution_log and self.execution_log[-1]["success"])
            memory.set_var(
                "{}_outcome".format(self.name),
                {
                    "ok": not any_unrecovered_failure,
                    "status": "completed",
                    "replans": replans_used,
                    "steps_executed": steps_executed,
                    "execution_log": list(self.execution_log),
                },
                desc="Structured outcome for PlanActAgent",
            )

        return memory

    def _extract_task(self, memory):
        """
        Extract the task from the last user message in memory.

        Args:
            memory: The MEMORY instance.

        Returns:
            str: The task text, or empty string if not found.
        """
        if hasattr(memory, "last_user_msg"):
            msg = memory.last_user_msg()
            if isinstance(msg, dict):
                return msg.get("content", "")
            return str(msg) if msg else ""
        return ""

    def _generate_plan(self, task):
        """
        Generate a structured plan for the given task.

        Calls the LLM with the planning prompt and parses the result as
        a JSON list of step objects.

        Args:
            task (str): The task to plan for.

        Returns:
            list[dict]: Plan steps, each with 'step', 'tool', 'args'.
                Empty list if planning fails.
        """
        tool_descriptions = []
        for t in self.tools:
            tool_descriptions.append("- {}: {}".format(t.name, t.description))
        tool_list = "\n".join(tool_descriptions) if tool_descriptions else "(none)"

        prompt = self.plan_prompt
        prompt = prompt.replace("{{task}}", task).replace("{task}", task)
        prompt = prompt.replace("{{tool_list}}", tool_list).replace("{tool_list}", tool_list)
        prompt = prompt.replace("{{}}", "{}")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        result = self.llm.call(messages)
        raw = result[0] if result else ""

        # Parse the plan from the LLM response
        try:
            plan = json.loads(raw)
            if isinstance(plan, list):
                return plan
        except (json.JSONDecodeError, TypeError):
            pass

        # Fenced JSON if top-level parse fails.
        try:
            message = self.plan_regex.search(raw)
            if message:
                plan = json.loads(message.group(1).strip())
                if isinstance(plan, list):
                    return plan
        except (json.JSONDecodeError, TypeError):
            pass

        return []

    def _summarize_remaining(self, original_task, failed_step_idx=None):
        """
        Summarize completed vs failed work so a replan avoids repeating broken steps.

        Args:
            original_task (str): The original task.
            failed_step_idx (int, optional): Legacy index parameter (unused; inspects
                full ``execution_log`` across replan rounds).

        Returns:
            str: A description of completed steps, last failure, and remaining work.
        """
        completed = [
            str(e["step"])
            for e in self.execution_log
            if e["success"] and e["step"] not in ("Plan", "Replan")
        ]
        failures = [
            "{} ({})".format(e["step"], e["result"])
            for e in self.execution_log
            if not e["success"]
        ]
        completed_desc = ", ".join(completed) if completed else "nothing"
        failure_desc = "; ".join(failures) if failures else "none"
        return (
            "Original task: {}. Completed so far: {}. "
            "Failed steps to work around: {}. Continue from where we left off."
        ).format(original_task, completed_desc, failure_desc)

    def _generate_summary(self, memory, task):
        """
        Generate a final summary of the plan execution.

        Args:
            memory: The MEMORY instance.
            task (str): The original task.

        Returns:
            str: Summary of results.
        """
        step_results = []
        for entry in self.execution_log:
            status = "done" if entry["success"] else "failed"
            step_results.append("- {} [{}]: {}".format(
                entry["step"], status, entry["result"][:100]
            ))

        steps_text = "\n".join(step_results) if step_results else "(no steps executed)"
        summary_prompt = (
            "Summarize the results of this task:\n"
            "Task: {}\n\nSteps completed:\n{}\n\n"
            "Provide a concise final answer."
        ).format(task, steps_text)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": summary_prompt},
        ]
        result = self.llm.call(messages)
        return result[0] if result else "Task completed."

    def __str__(self):
        """Return a concise string representation."""
        return "PlanActAgent({}, tools={}, replan={})".format(
            self.name, len(self.tools), self.replan_on_failure
        )

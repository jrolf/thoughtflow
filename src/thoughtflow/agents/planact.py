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
        "and 'args' (or {{}}).\n\nTask: {{task}}\n\n"
        "Available tools: {{tool_list}}"
    )

    def __init__(self, plan_prompt=None, replan_on_failure=True, **kwargs):
        """
        Initialize a PLANACT agent.

        Args:
            plan_prompt (str, optional): Prompt template for plan generation.
                Uses {task} and {tool_list} placeholders.
            replan_on_failure (bool): Whether to regenerate the plan when a
                step fails. Defaults to True.
            **kwargs: All other arguments passed to AGENT.__init__.
        """
        super().__init__(**kwargs)
        self.plan_prompt = plan_prompt or self.DEFAULT_PLAN_PROMPT
        self.replan_on_failure = replan_on_failure
        self.current_plan = []
        self.execution_log = []
        self.plan_regex = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

    def __call__(self, memory):
        """
        Run the plan-then-execute loop.

        1. Extract the task from the last user message
        2. Generate a plan
        3. Execute each step
        4. If a step fails and replan_on_failure is True, regenerate the plan
        5. Produce a final summary

        Args:
            memory: A MEMORY instance.

        Returns:
            MEMORY: Updated memory with execution results.
        """
        self.execution_log = []

        # Extract the task from the last user message
        task = self._extract_task(memory)
        if not task:
            if hasattr(memory, "add_msg"):
                memory.add_msg("assistant", "No task found to plan.")
            return memory

        # Generate the plan
        self.current_plan = self._generate_plan(task)

        if not self.current_plan:
            # Fall back to base agent behavior if planning fails
            return super().__call__(memory)

        self.execution_log.append({
            "step": "Plan",
            "tool": None,
            "result": json.dumps(self.current_plan),
            "success": True,
        })

        if hasattr(memory, "add_msg"):
            memory.add_msg("assistant", "Plan:\n" + json.dumps(self.current_plan))

        # Execute the plan
        for step_idx, step in enumerate(self.current_plan):
            step_desc = step.get("step", "Step {}".format(step_idx + 1))
            tool_name = step.get("tool")
            tool_args = step.get("args", {})

            if tool_name and tool_name in self._tool_map:
                result = self._execute_tool(tool_name, tool_args)
                success = not str(result).startswith("Error")

                self.execution_log.append({
                    "step": step_desc,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": str(result),
                    "success": success,
                })

                if hasattr(memory, "add_msg"):
                    memory.add_msg("assistant", "Step: {}\nResult: {}".format(
                        step_desc, result
                    ))

                # Replan if step failed
                if not success and self.replan_on_failure:
                    remaining_task = self._summarize_remaining(task, step_idx)
                    self.current_plan = self._generate_plan(remaining_task)
                    if self.current_plan:
                        self.execution_log.append({
                            "step": "Replan",
                            "tool": None,
                            "result": json.dumps(self.current_plan),
                            "success": True,
                        })
                        if hasattr(memory, "add_msg"):
                            memory.add_msg("assistant", "Replan:\n" + json.dumps(self.current_plan))
                        # Recursively execute the new plan (with reduced depth)
                        break
            else:
                # No tool needed — this is a reasoning step
                self.execution_log.append({
                    "step": step_desc,
                    "tool": None,
                    "result": "Reasoning step",
                    "success": True,
                })

        # Generate final summary
        summary = self._generate_summary(memory, task)
        if hasattr(memory, "add_msg"):
            memory.add_msg("assistant", summary)
        if hasattr(memory, "set_var"):
            memory.set_var(
                "{}_result".format(self.name), summary,
                desc="Final result from PlanActAgent"
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

        prompt = self.plan_prompt.replace("{{task}}", task)
        prompt = prompt.replace("{{tool_list}}", tool_list)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        result = self.llm.call(messages)
        raw = result[0] if result else ""

        plan = None

        # Parse the plan from the LLM response
        try:
            plan = json.loads(raw)
            if isinstance(plan, list):
                return plan
        except (json.JSONDecodeError, TypeError):
            pass

        # Fenced JSON if top-level parse is not a list (e.g. dict, or parse failed).
        if not isinstance(plan, list):
            try:
                message = self.plan_regex.search(raw)
                if message:
                    plan = json.loads(message.group(1).strip())
                    if isinstance(plan, list):
                        return plan
            except (json.JSONDecodeError, TypeError):
                pass

        return []

    def _summarize_remaining(self, original_task, failed_step_idx):
        """
        Summarize the remaining work after a step failure.

        Args:
            original_task (str): The original task.
            failed_step_idx (int): Index of the step that failed.

        Returns:
            str: A description of what still needs to be done.
        """
        completed = self.execution_log[:failed_step_idx]
        completed_desc = ", ".join(e["step"] for e in completed if e["success"])
        template = (
            "Original task: {}. Completed so far: {}. "
            "Continue from where we left off."
        )
        return template.format(original_task, completed_desc or "nothing")

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

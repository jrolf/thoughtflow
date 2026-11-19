"""
ReflectAgent for ThoughtFlow.

After producing a response, the ReflectAgent runs a self-critique step.
If the critique identifies issues, the agent revises its response. This
cycle continues until the critique passes or max revisions are exhausted.
"""

from __future__ import annotations

import re

from thoughtflow.agent import AGENT


class ReflectAgent(AGENT):
    """
    Self-critiquing agent that revises its own output.

    REFLECT extends AGENT by adding a reflection phase after the initial
    response. The agent:
    1. Generates a response (using the standard tool-use loop)
    2. Critiques its own response using a separate LLM call
    3. If the critique suggests revision, revises and returns to step 2
    4. If the critique passes, returns the response

    This is useful for tasks where quality matters more than speed, such
    as writing, analysis, and complex reasoning.

    Attributes:
        critique_prompt (str): The prompt template for the self-critique step.
            Should contain {response} as a placeholder for the response to critique.
        max_revisions (int): Maximum number of revision cycles. Defaults to 2.
        revision_history (list): Records of each critique/revision cycle.

    Example:
        >>> agent = REFLECT(
        ...     llm=llm,
        ...     system_prompt="You are a careful writer.",
        ...     max_revisions=2,
        ... )
        >>> memory = MEMORY()
        >>> memory.add_msg("user", "Write a haiku about programming.")
        >>> memory = agent(memory)
    """

    DEFAULT_CRITIQUE_PROMPT = (
        "Review the following response and identify any issues with accuracy, "
        "completeness, clarity, or quality. If the response is good, say "
        "'APPROVED'. If it needs improvement, explain what should be changed.\n\n"
        "Task:\n{task}\n\n"
        "Response to review:\n{response}"
    )

    # Phrases that mean "do not approve" even when they contain an approval word.
    REJECT_SIGNALS = (
        "not approved", "do not approve", "don't approve", "cannot approve",
        "can't approve", "not approve", "needs improvement", "need improvement",
        "needs revision", "revise", "not good", "unacceptable",
    )

    def __init__(self, critique_prompt=None, max_revisions=2, **kwargs):
        """
        Initialize a REFLECT agent.

        Args:
            critique_prompt (str, optional): Prompt for the self-critique step.
                May contain ``{response}`` (required in practice), ``{task}`` (the
                latest user message), and ``{system_prompt}``. Prompts that only
                use ``{response}`` keep working. Uses a sensible default.
            max_revisions (int): Max critique/revision cycles. Defaults to 2.
            **kwargs: All other arguments passed to AGENT.__init__.
        """
        super().__init__(**kwargs)
        self.critique_prompt = critique_prompt or self.DEFAULT_CRITIQUE_PROMPT
        self.max_revisions = max_revisions
        self.revision_history = []
        self.final_critique = None

    def __call__(self, memory, decision=None):
        """
        Run the REFLECT loop: generate, critique, revise.

        Args:
            memory: A MEMORY instance.
            decision (dict, optional): Forwarded to the base loop to resume a
                suspended native tool run.

        Returns:
            MEMORY: Updated memory with the (possibly revised) response.
        """
        self.revision_history = []
        self.final_critique = None

        # Step 1: Generate initial response using the base agent loop
        memory = super().__call__(memory, decision=decision)

        if hasattr(memory, "is_suspended") and memory.is_suspended():
            return memory

        task = self._task_text(memory)

        # Get the initial response
        result_key = "{}_result".format(self.name)
        current_response = ""
        if hasattr(memory, "get_var"):
            current_response = memory.get_var(result_key) or ""

        if not current_response:
            return memory

        # Step 2: Critique and revise loop
        approved = False
        for revision_num in range(self.max_revisions):
            critique = self._critique(current_response, task)

            self.revision_history.append({
                "revision": revision_num + 1,
                "response": current_response,
                "critique": critique,
            })

            if self._should_approve(critique):
                approved = True
                break

            # Revise based on the critique
            current_response = self._revise(memory, current_response, critique)

            # Update memory with the revised response
            if hasattr(memory, "set_var"):
                memory.set_var(
                    result_key, current_response,
                    desc="Revised response (revision {})".format(revision_num + 1)
                )
            if hasattr(memory, "add_msg"):
                memory.add_msg("assistant", current_response)

        # Final verification: when revisions ran out, judge the last revision
        # so the outcome says whether the delivered answer was ever approved.
        if not approved and len(self.revision_history) > 0 and self.max_revisions > 0:
            critique = self._critique(current_response, task)
            approved = self._should_approve(critique)
            self.final_critique = critique

        if hasattr(memory, "set_var"):
            outcome = dict(memory.get_var("{}_outcome".format(self.name)) or {})
            outcome["approved"] = approved
            outcome["revisions"] = len(self.revision_history)
            outcome["final_critique"] = self.final_critique
            memory.set_var(
                "{}_outcome".format(self.name), outcome,
                desc="Structured outcome for agent: {}".format(self.name),
            )

        return memory

    @staticmethod
    def _task_text(memory):
        """The latest user message, used to tell the critic what was asked."""
        if hasattr(memory, "last_user_msg"):
            return memory.last_user_msg(content_only=True) or ""
        return ""

    def _critique(self, response, task=""):
        """
        Run the self-critique step on a response.

        Calls the LLM with the critique prompt to evaluate the response.

        Args:
            response (str): The response to critique.
            task (str): The user's request the response is answering.

        Returns:
            str: The critique text.
        """
        prompt = self.critique_prompt
        for token, value in (
            ("{task}", task),
            ("{system_prompt}", self.system_prompt or ""),
            ("{response}", response),
        ):
            prompt = prompt.replace(token, value)
        messages = [{"role": "user", "content": prompt}]
        result = self.llm.call(messages)
        return result[0] if result else ""

    def _should_approve(self, critique):
        """
        Determine if the critique approves the response.

        Looks for approval indicators in the critique text.

        Args:
            critique (str): The critique text.

        Returns:
            bool: True if the response is approved.
        """
        critique_lower = critique.lower().strip()
        if any(signal in critique_lower for signal in self.REJECT_SIGNALS):
            return False
        # Word boundaries keep "unapproved" and "disapproved" from counting.
        return re.search(
            r"\bapproved\b|\blooks good\b|\bno issues\b|\bno changes needed\b",
            critique_lower,
        ) is not None

    def _revise(self, memory, current_response, critique):
        """
        Revise the response based on the critique.

        Calls the LLM with the original context, the current response, and
        the critique to produce an improved version.

        Args:
            memory: The MEMORY instance with original context.
            current_response (str): The response to revise.
            critique (str): The critique identifying issues.

        Returns:
            str: The revised response.
        """
        revision_prompt = (
            "Your previous response was:\n{}\n\n"
            "It received this critique:\n{}\n\n"
            "Please provide an improved response that addresses the critique."
        ).format(current_response, critique)

        messages = self._build_messages(memory)
        messages.append({"role": "user", "content": revision_prompt})

        result = self.llm.call(messages)
        return result[0] if result else current_response

    def __str__(self):
        """Return a concise string representation."""
        return "ReflectAgent({}, max_revisions={})".format(self.name, self.max_revisions)

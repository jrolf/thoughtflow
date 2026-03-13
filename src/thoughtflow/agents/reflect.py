"""
ReflectAgent for ThoughtFlow.

After producing a response, the ReflectAgent runs a self-critique step.
If the critique identifies issues, the agent revises its response. This
cycle continues until the critique passes or max revisions are exhausted.
"""

from __future__ import annotations

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
        "Response to review:\n{response}"
    )

    def __init__(self, critique_prompt=None, max_revisions=2, **kwargs):
        """
        Initialize a REFLECT agent.

        Args:
            critique_prompt (str, optional): Prompt for the self-critique step.
                Must contain {response} placeholder. Uses a sensible default.
            max_revisions (int): Max critique/revision cycles. Defaults to 2.
            **kwargs: All other arguments passed to AGENT.__init__.
        """
        super().__init__(**kwargs)
        self.critique_prompt = critique_prompt or self.DEFAULT_CRITIQUE_PROMPT
        self.max_revisions = max_revisions
        self.revision_history = []

    def __call__(self, memory):
        """
        Run the REFLECT loop: generate, critique, revise.

        Args:
            memory: A MEMORY instance.

        Returns:
            MEMORY: Updated memory with the (possibly revised) response.
        """
        self.revision_history = []

        # Step 1: Generate initial response using the base agent loop
        memory = super().__call__(memory)

        # Get the initial response
        result_key = "{}_result".format(self.name)
        current_response = ""
        if hasattr(memory, "get_var"):
            current_response = memory.get_var(result_key) or ""

        if not current_response:
            return memory

        # Step 2: Critique and revise loop
        for revision_num in range(self.max_revisions):
            critique = self._critique(current_response)

            self.revision_history.append({
                "revision": revision_num + 1,
                "response": current_response,
                "critique": critique,
            })

            if self._should_approve(critique):
                break

            # Revise based on the critique
            current_response = self._revise(memory, current_response, critique)

            # Update memory with the revised response
            if hasattr(memory, "set_var"):
                memory.set_var(
                    result_key, current_response,
                    desc="Revised response (revision {})".format(revision_num + 1)
                )

        return memory

    def _critique(self, response):
        """
        Run the self-critique step on a response.

        Calls the LLM with the critique prompt to evaluate the response.

        Args:
            response (str): The response to critique.

        Returns:
            str: The critique text.
        """
        prompt = self.critique_prompt.format(response=response)
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
        approval_signals = ["approved", "looks good", "no issues", "no changes needed"]
        return any(signal in critique_lower for signal in approval_signals)

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

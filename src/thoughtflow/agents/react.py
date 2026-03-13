"""
ReactAgent for ThoughtFlow.

Implements the Reason + Act (ReAct) methodology where each iteration
explicitly structures the LLM's output into:
    Thought: (reasoning about what to do)
    Action: (tool to call with arguments)
    Observation: (result from the tool)

The loop continues until the LLM produces a "Final Answer" instead of
an Action, or the iteration limit is reached.
"""

from __future__ import annotations

import json

from thoughtflow.agent import AGENT


class ReactAgent(AGENT):
    """
    ReAct (Reason + Act) agent loop.

    Extends AGENT by injecting ReAct-specific formatting into the system
    prompt and parsing the LLM's structured Thought/Action/Observation output.
    The LLM is instructed to reason step-by-step, choose a tool, observe the
    result, and repeat until it can provide a Final Answer.

    The ReAct loop:
    1. LLM outputs a Thought (reasoning)
    2. LLM outputs an Action (tool name + args) OR a Final Answer
    3. If Action: execute the tool, add the Observation to context, go to 1
    4. If Final Answer: store it and stop

    Example:
        >>> agent = REACT(
        ...     llm=llm,
        ...     tools=[search_tool, calculator_tool],
        ...     system_prompt="You are a problem-solving assistant.",
        ... )
        >>> memory = MEMORY()
        >>> memory.add_msg("user", "What is 23 * 47?")
        >>> memory = agent(memory)
    """

    # The suffix injected into the system prompt to enforce ReAct formatting
    REACT_INSTRUCTIONS = """

You must follow this exact format for each step:

Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON arguments for the tool>

After receiving an Observation (tool result), continue with another Thought.

When you have enough information to answer, respond with:

Thought: <your final reasoning>
Final Answer: <your complete answer to the user>

Available tools: {tool_list}
"""

    def _build_messages(self, memory):
        """
        Build messages with ReAct-specific system prompt formatting.

        Injects the ReAct instructions and available tool descriptions into
        the system prompt so the LLM knows the expected output format.

        Args:
            memory: The MEMORY instance.

        Returns:
            list[dict]: Messages with ReAct formatting.
        """
        tool_descriptions = []
        for t in self.tools:
            params_desc = json.dumps(t.parameters.get("properties", {}))
            tool_descriptions.append("- {}: {} (params: {})".format(
                t.name, t.description, params_desc
            ))
        tool_list = "\n".join(tool_descriptions) if tool_descriptions else "(none)"

        react_prompt = self.system_prompt + self.REACT_INSTRUCTIONS.format(
            tool_list=tool_list
        )

        messages = [{"role": "system", "content": react_prompt}]

        if hasattr(memory, "get_msgs"):
            for msg in memory.get_msgs():
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        return messages

    def _build_params(self):
        """
        Build LLM params for ReAct. No tool schemas needed — ReAct uses
        text-based tool selection rather than function-calling API.

        Returns:
            dict: Empty params (ReAct relies on prompt, not tool schemas).
        """
        return {}

    def _parse_tool_calls(self, response):
        """
        Parse ReAct-formatted text for Action / Final Answer.

        Looks for:
        - "Action: <tool_name>" and "Action Input: <json>" lines
        - "Final Answer:" to indicate completion

        Args:
            response (str): The LLM's text response.

        Returns:
            list[dict]: Parsed tool calls, or empty list for Final Answer.
        """
        if not response:
            return []

        lines = response.strip().split("\n")

        action_name = None
        action_input = {}

        for line in lines:
            stripped = line.strip()

            if stripped.lower().startswith("final answer:"):
                # Extract the final answer and signal no more tool calls
                return []

            if stripped.startswith("Action:"):
                action_name = stripped[len("Action:"):].strip()

            if stripped.startswith("Action Input:"):
                raw_input = stripped[len("Action Input:"):].strip()
                try:
                    action_input = json.loads(raw_input)
                except json.JSONDecodeError:
                    action_input = {"input": raw_input}

        if action_name:
            return [{"name": action_name, "arguments": action_input}]

        return []

    def __call__(self, memory):
        """
        Run the ReAct loop on the given memory.

        Overrides the base AGENT loop to handle ReAct-specific response
        parsing: extracting Thoughts, Actions, and Final Answers from
        the LLM's text output.

        Args:
            memory: A MEMORY instance.

        Returns:
            MEMORY: Updated memory with the agent's reasoning and response.
        """
        self.iteration_count = 0

        for _ in range(self.max_iterations):
            self.iteration_count += 1

            messages = self._build_messages(memory)
            params = self._build_params()
            response = self.llm.call(messages, params)
            raw_response = response[0] if response else ""

            tool_calls = self._parse_tool_calls(raw_response)

            if not tool_calls:
                # Final Answer or no action found — extract the answer
                final_answer = raw_response
                for line in raw_response.split("\n"):
                    if line.strip().lower().startswith("final answer:"):
                        final_answer = line.strip()[len("Final Answer:"):].strip()
                        break

                if hasattr(memory, "add_msg"):
                    memory.add_msg("assistant", final_answer)
                if hasattr(memory, "set_var"):
                    memory.set_var(
                        "{}_result".format(self.name), final_answer,
                        desc="Final answer from ReactAgent: {}".format(self.name)
                    )
                break

            # Execute tool calls
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                arguments = tc.get("arguments", {})

                if self.on_tool_call:
                    proceed = self.on_tool_call(tool_name, arguments)
                    if proceed is False:
                        continue

                result = self._execute_tool(tool_name, arguments)

                # Add the full ReAct trace to memory
                if hasattr(memory, "add_msg"):
                    memory.add_msg("assistant", raw_response)
                    memory.add_msg("user", "Observation: {}".format(result))
        else:
            if hasattr(memory, "add_log"):
                memory.add_log("ReactAgent reached max iterations.")

        return memory

    def __str__(self):
        """Return a concise string representation."""
        return "ReactAgent({}, tools={})".format(self.name, len(self.tools))

"""
AGENT class for ThoughtFlow.

AGENT is the autonomous execution loop — the primitive that makes an LLM into
an agent. It combines an LLM, a set of TOOLs, and a MEMORY, and runs the cycle:

    call LLM → LLM requests tool calls → execute tools → feed results back → repeat

This continues until the LLM produces a final text response (no tool calls)
or a configurable iteration limit is reached.

AGENT is the base class. Subclasses (ReactAgent, ReflectAgent, PlanActAgent) override specific
parts of the loop to implement different agentic methodologies.
"""

from __future__ import annotations

import json

from thoughtflow._util import event_stamp


class AGENT:
    """
    Autonomous tool-use loop for LLM-driven agents.

    AGENT orchestrates the core agentic cycle: call the LLM with tool schemas,
    parse any tool-call requests from the response, execute those tools, inject
    results back into the conversation, and repeat until the LLM produces a
    final response or the iteration limit is reached.

    Preserves the Thoughtflow contract: memory = agent(memory).

    Attributes:
        name (str): Identifier for this agent.
        llm: The LLM instance to use for generation.
        tools (list[TOOL]): Available tools the LLM can select from.
        system_prompt (str): System prompt providing the agent's role/instructions.
        max_iterations (int): Maximum tool-use loop iterations before stopping.
        on_tool_call (callable, optional): Hook called before each tool execution.
            Receives (tool_name, arguments) and can return False to block execution.
        id (str): Unique identifier for this agent instance.
        iteration_count (int): Number of iterations in the most recent run.
        LLM_ROLES (set): Class-level set of MEMORY roles that should be forwarded
            to the LLM.  Roles not in this set (e.g. 'reflection', 'query',
            'logger') are filtered out by _build_messages().  Subclasses can
            override this to include additional roles.

    Example:
        >>> from thoughtflow import LLM, MEMORY, TOOL, AGENT
        >>> llm = LLM("openai:gpt-4o", key="sk-...")
        >>> tools = [TOOL("search", "Search the web", {...}, search_fn)]
        >>> agent = AGENT(llm=llm, tools=tools, system_prompt="You are helpful.")
        >>> memory = MEMORY()
        >>> memory.add_msg("user", "What is the weather in Paris?")
        >>> memory = agent(memory)
        >>> print(memory.last_asst_msg())
    """

    # MEMORY roles that are relevant for LLM conversation context.
    # The LLM's _prepare_messages() handles translating these into
    # provider-native role strings (e.g. "action" → "tool" for OpenAI).
    LLM_ROLES = {'user', 'assistant', 'system', 'action', 'result'}

    def __init__(
        self,
        llm=None,
        tools=None,
        system_prompt="You are a helpful assistant.",
        max_iterations=10,
        name="agent",
        on_tool_call=None,
    ):
        """
        Initialize an AGENT with an LLM, tools, and configuration.

        Args:
            llm: An LLM instance for making model calls. Required.
            tools (list[TOOL], optional): Tools available to the agent.
            system_prompt (str): System-level instructions for the agent.
            max_iterations (int): Max tool-use iterations before forced stop.
                Prevents runaway loops. Defaults to 10.
            name (str): Identifier for logging and tracing.
            on_tool_call (callable, optional): Pre-execution hook. Called as
                on_tool_call(tool_name, arguments). Return False to block.
        """
        self.name = name
        self.id = event_stamp()
        self.llm = llm
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.on_tool_call = on_tool_call
        self.iteration_count = 0
        self._tool_map = {t.name: t for t in self.tools}

    def __call__(self, memory):
        """
        Run the autonomous agent loop on the given memory.

        The loop:
        1. Build messages from memory (system prompt + conversation history)
        2. Call the LLM with tool schemas
        3. If the LLM requests tool calls, execute them and add results to memory
        4. Repeat from step 1 until the LLM responds without tool calls or
           max_iterations is reached

        Args:
            memory: A MEMORY instance with the conversation so far.

        Returns:
            MEMORY: The updated memory with the agent's response and any
                tool call/result history added.
        """
        self.iteration_count = 0

        for _ in range(self.max_iterations):
            self.iteration_count += 1

            messages = self._build_messages(memory)
            params = self._build_params()

            response = self.llm.call(messages, params)

            # The LLM returns a list; take the first response
            raw_response = response[0] if response else ""

            # Check if the response contains tool calls
            tool_calls = self._parse_tool_calls(raw_response)

            if not tool_calls:
                # No tool calls — this is the final response
                if hasattr(memory, "add_msg"):
                    memory.add_msg("assistant", raw_response)
                if hasattr(memory, "set_var"):
                    memory.set_var(
                        "{}_result".format(self.name), raw_response,
                        desc="Final response from agent: {}".format(self.name)
                    )
                break

            # Execute each tool call and add results to memory
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                arguments = tc.get("arguments", {})

                # Run pre-execution hook
                if self.on_tool_call:
                    proceed = self.on_tool_call(tool_name, arguments)
                    if proceed is False:
                        if hasattr(memory, "add_log"):
                            msg = "Tool call blocked by hook: {}".format(tool_name)
                            memory.add_log(msg)
                        continue

                result = self._execute_tool(tool_name, arguments)

                # Add the tool interaction to memory for context.
                # Uses "action" role for the tool request and "result" role
                # for the tool output — these are valid MEMORY roles.
                if hasattr(memory, "add_msg"):
                    memory.add_msg("action", json.dumps({
                        "tool_call": {"name": tool_name, "arguments": arguments}
                    }))
                    memory.add_msg("result", json.dumps({
                        "name": tool_name,
                        "result": str(result),
                    }))
        else:
            # Max iterations reached without a final response
            if hasattr(memory, "add_log"):
                memory.add_log("Agent '{}' reached max iterations ({}).".format(
                    self.name, self.max_iterations
                ))

        return memory

    def _build_messages(self, memory):
        """
        Construct the message list for the LLM from memory.

        Builds the conversation context: system prompt first, then messages
        from memory whose role is in LLM_ROLES.  Messages with roles outside
        that set (e.g. 'reflection', 'query', 'logger') are intentionally
        omitted — MEMORY may store many role types, but only conversation-
        relevant ones should be forwarded to the LLM.

        Subclasses can override this to inject methodology-specific prompts
        (e.g., ReAct formatting), or override LLM_ROLES to include
        additional roles.

        Args:
            memory: The MEMORY instance.

        Returns:
            list[dict]: Messages in LLM-ready format.
        """
        messages = []

        # System prompt
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # Conversation history from memory (filtered to LLM-relevant roles)
        if hasattr(memory, "get_msgs"):
            for msg in memory.get_msgs():
                role = msg.get("role", "user")
                if role not in self.LLM_ROLES:
                    continue
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

        return messages

    def _build_params(self):
        """
        Build LLM call parameters, including tool schemas.

        Formats the tool list into the 'tools' parameter that OpenAI-compatible
        APIs expect. Subclasses can override to add methodology-specific params.

        Returns:
            dict: Parameters for the LLM call.
        """
        params = {}
        if self.tools:
            params["tools"] = [t.to_schema() for t in self.tools]
        return params

    def _strip_markdown_backticks(self, response):
        """
        Strip markdown backticks from the response.
        """
        return response.replace("```", "").replace("`", "")

    def _parse_tool_calls(self, response):
        """
        Extract tool-call requests from an LLM response.

        LLMs may embed tool calls in different formats. This method tries:
        1. JSON with a "tool_call" or "tool_calls" key
        2. JSON with a "name" and "arguments" structure
        3. Plain text (no tool calls)

        Subclasses can override for methodology-specific parsing.

        Args:
            response (str): The raw LLM response text.

        Returns:
            list[dict]: Tool call requests, each with 'name' and 'arguments'.
                Empty list if no tool calls are found.
        """
        if not response:
            return []

        # Strip markdown backticks for better JSON parsing.
        response = self._strip_markdown_backticks(response)

        # Try to parse as JSON
        try:
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return []

        # Format: {"tool_calls": [{"name": "...", "arguments": {...}}, ...]}
        if isinstance(data, dict) and "tool_calls" in data:
            calls = data["tool_calls"]
            if isinstance(calls, list):
                return calls

        # Format: {"tool_call": {"name": "...", "arguments": {...}}}
        if isinstance(data, dict) and "tool_call" in data:
            tc = data["tool_call"]
            if isinstance(tc, dict) and "name" in tc:
                return [tc]

        # Format: {"name": "...", "arguments": {...}} (single tool call)
        if isinstance(data, dict) and "name" in data and "arguments" in data:
            return [data]

        return []

    def _execute_tool(self, tool_name, arguments):
        """
        Execute a single tool by name with the given arguments.

        Looks up the tool in the agent's tool map and calls it. If the tool
        is not found, returns an error message.

        Args:
            tool_name (str): Name of the tool to execute.
            arguments (dict): Arguments for the tool.

        Returns:
            The tool's result, or an error string if the tool is not found
            or execution fails.
        """
        tool = self._tool_map.get(tool_name)
        if not tool:
            return "Error: Tool '{}' not found.".format(tool_name)

        try:
            return tool(arguments)
        except Exception as e:
            return "Error executing tool '{}': {}".format(tool_name, str(e))

    def __str__(self):
        """Return a concise string representation."""
        return "AGENT({}, tools={})".format(self.name, len(self.tools))

    def __repr__(self):
        """Return a detailed string representation."""
        tool_names = [t.name for t in self.tools]
        return "AGENT(name='{}', tools={}, max_iterations={})".format(
            self.name, tool_names, self.max_iterations
        )

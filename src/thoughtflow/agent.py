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
import re

from thoughtflow._util import event_stamp
from thoughtflow.llm_chat import CHAT_SERVICES

_FENCED_JSON_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


class AGENT:
    """
    Autonomous tool-use loop for LLM-driven agents.

    AGENT orchestrates the core agentic cycle: call the LLM with tool schemas,
    parse any tool-call requests from the response, execute those tools, inject
    results back into the conversation, and repeat until the LLM produces a
    final response or the iteration limit is reached.

    Preserves the ThoughtFlow contract: memory = agent(memory).

    Attributes:
        name (str): Identifier for this agent.
        llm: The LLM instance to use for generation.
        tools (list[TOOL]): Available tools the LLM can select from.
        system_prompt (str): System prompt providing the agent's role/instructions.
        max_iterations (int): Maximum tool-use loop iterations before stopping.
        on_tool_call (callable, optional): Hook called before each tool execution.
            Receives (tool_name, arguments) and can return False to block execution.
        merge_augments (bool): When True, fold augmenting memory events into user
            messages for LLM calls only (via ``MEMORY.get_llm_msgs``). Default
            False preserves separate system/context messages in the LLM payload.
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
        merge_augments=False,
        allow=None,
        policy=None,
        budget=None,
        checkpoint=None,
        protocol="auto",
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
            merge_augments (bool): Fold augmenting memory events into user
                messages for LLM calls only. Default False.
            allow (list[str], optional): Tool names the model may run. Calls to
                any other tool get an error ``tool`` message instead.
            policy (dict or callable, optional): Governance per tool. A dict maps
                tool name (or ``"*"``) to ``"allow"``, ``"deny"``, ``"approve"``,
                or ``{"mode": "approve_over", "field": "amount", "limit": 100}``.
                A callable ``policy(name, arguments)`` returns the same values.
                ``{"mode": "deny", "halt": True}`` ends the run as ``vetoed``.
            budget (dict, optional): Hard limits ``max_model_calls``,
                ``max_tool_calls``, ``max_tokens`` (prompt + completion).
            checkpoint (callable, optional): ``checkpoint(memory)`` called after
                the assistant tool_calls are written and after every tool result.
            protocol (str): ``"native"`` (``llm.chat`` tool calls), ``"text"``
                (JSON tool calls parsed from ``llm.call`` text), or ``"auto"``
                (native when the llm has ``chat``, otherwise text). Governance
                options need the native protocol.
        """
        if protocol not in ("auto", "native", "text"):
            raise ValueError("protocol must be 'auto', 'native', or 'text', got: {!r}".format(protocol))
        self.allow = list(allow) if allow is not None else None
        self.policy = policy
        self.budget = dict(budget or {})
        self.checkpoint = checkpoint
        self.protocol = protocol
        self.name = name
        self.id = event_stamp()
        self.llm = llm
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.on_tool_call = on_tool_call
        self.merge_augments = merge_augments
        self.iteration_count = 0
        self._tool_map = {t.name: t for t in self.tools}

    def _governed(self):
        """True when any governance option needs the native protocol."""
        return bool(
            self.allow is not None or self.policy or self.budget or self.checkpoint
        )

    def _use_native(self):
        """Resolve ``protocol`` to a boolean for this run."""
        if self.protocol == "native":
            return True
        if self.protocol == "text":
            return False
        if self.llm is not None and callable(getattr(self.llm, "chat", None)):
            # ThoughtFlow's LLM has chat() for every service, but only some
            # services support it; unknown custom objects with chat() are trusted.
            service = getattr(self.llm, "service", None)
            if service is None or service in CHAT_SERVICES:
                return True
        if self._governed():
            raise ValueError(
                "allow/policy/budget/checkpoint need native tool calls, but this llm has no "
                "usable chat() (LLM.chat supports the openai, openrouter and groq services). "
                "Use one of those or drop the governance options."
            )
        return False

    def __call__(self, memory, decision=None):
        """
        Run the agent loop; native tool calls when available, else text JSON.

        Args:
            memory: A MEMORY instance with the conversation so far.
            decision (dict, optional): Resolution for a suspended run, for
                example ``{"approve": True}``. Only used by the native protocol.

        Returns:
            MEMORY: The updated memory. ``{name}_status`` records how the run
            ended: final, suspended, max_iterations, budget_exhausted, vetoed,
            or error.
        """
        if self._use_native():
            return self._run_native(memory, decision)
        return self._run_text(memory)

    def _run_text(self, memory):
        """
        Run the legacy text-protocol agent loop on the given memory.

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
            self._emit_usage_on_memory(memory, getattr(self.llm, "last_usage", None))

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

                result = self._execute_tool(
                    tool_name,
                    arguments,
                    context={"call_id": None, "memory": memory, "agent": self},
                )

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

    def _iter_memory_msgs_for_llm(self, memory):
        """
        Yield (role, content) pairs from memory for LLM conversation context.

        When ``merge_augments`` is True and memory supports ``get_llm_msgs``,
        augmenting events are folded into user messages for the LLM view only.
        """
        if self.merge_augments and hasattr(memory, "get_llm_msgs"):
            source = memory.get_llm_msgs(merge_augments=True)
        elif hasattr(memory, "get_msgs"):
            source = [
                {'role': msg.get('role', 'user'), 'content': msg.get('content', '')}
                for msg in memory.get_msgs()
            ]
        else:
            return

        for msg in source:
            role = msg.get('role', 'user')
            if role in self.LLM_ROLES:
                yield role, msg.get('content', '')

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

        for role, content in self._iter_memory_msgs_for_llm(memory):
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

    @staticmethod
    def _strip_markdown_fences(response):
        """
        Strip wrapping markdown code fences from an LLM response.

        Only removes outer ``` / ```json fences. Inline backticks inside JSON
        string values are left untouched.
        """
        if not response:
            return response

        match = _FENCED_JSON_RE.match(response)
        if match:
            return match.group(1).strip()

        return response

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

        response = self._strip_markdown_fences(response)

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

    def _execute_tool(self, tool_name, arguments, context=None):
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
            return tool(arguments, context=context)
        except Exception as e:
            return "Error executing tool '{}': {}".format(tool_name, str(e))

    # ------------------------------------------------------------------
    # Native tool-call protocol (write-ahead, governed, resumable)
    # ------------------------------------------------------------------

    def _run_native(self, memory, decision=None):
        """
        Run the native ``llm.chat`` tool loop.

        Contract: the assistant message with its ``tool_calls`` is written to
        MEMORY before any tool runs, every ``tool_call_id`` is answered (even
        when vetoed), and pending work is derived from the transcript, so a
        crashed or suspended run resumes exactly where it stopped.
        """
        state = self._load_run_state(memory)
        self.iteration_count = 0
        status = None

        if memory.is_suspended():
            if decision is None:
                return self._finish(memory, "suspended", state)
            record = memory.resolve_suspension(decision)["suspension"]
            decision = record.get("decision") if record else decision

        pending = self._unanswered_calls(memory)
        if pending:
            status = self._process_calls(memory, pending, decision, state)

        iterations = 0
        while status is None:
            if iterations >= self.max_iterations:
                status = "max_iterations"
                memory.add_log("Agent '{}' reached max iterations ({}).".format(
                    self.name, self.max_iterations
                ))
                break
            if self._over_budget(state, "max_model_calls", "model_calls", extra=0):
                status = "budget_exhausted"
                break
            iterations += 1
            self.iteration_count = iterations

            messages = self._native_messages(memory)
            tools = [t.to_schema() for t in self.tools] or None
            try:
                message = self.llm.chat(messages, tools=tools)
            except Exception as e:
                memory.add_log("Agent '{}' model error: {}".format(self.name, e))
                state["error"] = str(e)
                status = "error"
                break
            state["model_calls"] += 1
            self._add_usage(state, message.get("usage"))
            self._emit_usage_on_memory(memory, message.get("usage"))

            calls = list(message.get("tool_calls") or [])
            content = message.get("content") or ""
            if not calls:
                memory.add_msg("assistant", content)
                memory.set_var(
                    "{}_result".format(self.name), content,
                    desc="Final response from agent: {}".format(self.name),
                )
                status = "final"
                break

            stamp = event_stamp()[:8]
            for idx, call in enumerate(calls):
                if not call.get("id"):
                    call["id"] = "call_{}_{}".format(stamp, idx)
            memory.add_msg("assistant", content, tool_calls=calls)
            self._run_checkpoint(memory)
            if self._over_budget(state, "max_tokens", "total_tokens", extra=0):
                self._answer_remaining(memory, calls, "Error: token budget exhausted.")
                status = "budget_exhausted"
                break
            status = self._process_calls(memory, self._unanswered_calls(memory), None, state)

        return self._finish(memory, status, state)

    def _native_messages(self, memory):
        """System prompt plus provider-valid history for ``llm.chat``."""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(
            memory.get_llm_msgs(format="openai", merge_augments=self.merge_augments)
        )
        return messages

    @staticmethod
    def _unanswered_calls(memory):
        """Tool calls in the latest assistant tool_calls message with no tool result yet."""
        msgs = memory.get_msgs(include=["assistant", "tool"])
        last_idx = None
        for i, msg in enumerate(msgs):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                last_idx = i
        if last_idx is None:
            return []
        answered = {
            m.get("tool_call_id") for m in msgs[last_idx + 1:] if m.get("role") == "tool"
        }
        return [tc for tc in msgs[last_idx]["tool_calls"] if tc.get("id") not in answered]

    def _load_run_state(self, memory):
        """Counters for budgets; carried over when resuming a suspended run."""
        state = {
            "model_calls": 0, "tool_calls": 0, "total_tokens": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "vetoed": 0, "error": None,
        }
        prior = memory.get_var("{}_outcome".format(self.name)) or {}
        if prior.get("status") == "suspended":
            for key in state:
                if key in prior and key != "error":
                    state[key] = prior[key]
        return state

    def _emit_usage_on_memory(self, memory, usage):
        """Emit a ``'usage'`` event onto ``memory`` unless already emitted via ``llm.record(memory)``."""
        if not isinstance(usage, dict) or not usage:
            return
        if not hasattr(memory, "emit") or not callable(getattr(memory, "emit", None)):
            return
        rec_mem = getattr(self.llm, "_record_memory", None)
        root_mem = getattr(memory, "base", memory)
        root_rec = getattr(rec_mem, "base", rec_mem) if rec_mem is not None else None
        if root_rec is not None and root_mem is root_rec:
            return
        payload = dict(usage)
        payload["agent"] = self.name
        memory.emit("usage", payload)

    @staticmethod
    def _add_usage(state, usage):
        """Accumulate provider usage into run state."""
        if not isinstance(usage, dict):
            return
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        state["prompt_tokens"] += prompt
        state["completion_tokens"] += completion
        state["total_tokens"] += prompt + completion

    def _over_budget(self, state, limit_key, counter_key, extra=0):
        """True when ``counter + extra`` would exceed the configured limit."""
        limit = self.budget.get(limit_key)
        if limit is None:
            return False
        return state[counter_key] + extra >= limit

    def _run_checkpoint(self, memory):
        """Invoke the user checkpoint hook, never letting it break the run."""
        if self.checkpoint is None:
            return
        try:
            self.checkpoint(memory)
        except Exception as e:
            memory.add_log("Agent '{}' checkpoint error: {}".format(self.name, e))

    def _answer_remaining(self, memory, calls, text):
        """Give every still-unanswered call a tool message (strict providers need it)."""
        answered = {
            m.get("tool_call_id") for m in memory.get_msgs(include=["tool"])
        }
        for call in calls:
            if call.get("id") not in answered:
                memory.add_msg("tool", text, tool_call_id=call["id"], name=call.get("name"))
        self._run_checkpoint(memory)

    def _policy_for(self, name, arguments):
        """Resolve the policy entry for one call into ``(mode, spec)``."""
        entry = None
        if callable(self.policy):
            entry = self.policy(name, arguments)
        elif isinstance(self.policy, dict):
            entry = self.policy.get(name, self.policy.get("*"))
        if entry is None:
            return "allow", {}
        if isinstance(entry, str):
            return entry, {}
        return entry.get("mode", "allow"), entry

    def _needs_approval(self, mode, spec, arguments):
        """True when the policy mode demands a human decision for these arguments."""
        if mode == "approve":
            return True
        if mode == "approve_over":
            try:
                return float((arguments or {}).get(spec.get("field"), 0)) > float(spec.get("limit", 0))
            except (TypeError, ValueError):
                return True
        return False

    @staticmethod
    def _approved(decision, call_id):
        """Interpret a resume decision for one call id."""
        if not isinstance(decision, dict) or "approve" not in decision:
            return None
        verdict = decision["approve"]
        if isinstance(verdict, dict):
            return verdict.get(call_id)
        if isinstance(verdict, (list, tuple, set)):
            return call_id in verdict
        return bool(verdict)

    def _process_calls(self, memory, calls, decision, state):
        """
        Answer each pending tool call; return a terminal status or ``None``.

        ``None`` means every call was answered and the model should run again.
        """
        for idx, call in enumerate(calls):
            call_id = call.get("id")
            name = call.get("name", "")
            arguments = call.get("arguments") or {}
            if isinstance(call.get("function"), dict):
                # Wire-format call (hand-built or imported transcript).
                name = call["function"].get("name", "")
                raw = call["function"].get("arguments", "")
                try:
                    arguments = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
                except ValueError as e:
                    call = dict(call, arguments_error=str(e))

            def answer(text):
                memory.add_msg("tool", text, tool_call_id=call_id, name=name)
                self._run_checkpoint(memory)

            if call.get("arguments_error"):
                answer("Error: invalid arguments for '{}': {}".format(name, call["arguments_error"]))
                continue
            if name not in self._tool_map or (self.allow is not None and name not in self.allow):
                answer("Error: tool '{}' is not available.".format(name))
                continue
            if self.on_tool_call and self.on_tool_call(name, arguments) is False:
                state["vetoed"] += 1
                memory.add_log("Tool call blocked by hook: {}".format(name))
                answer("Blocked: '{}' was not permitted by the host.".format(name))
                continue

            mode, spec = self._policy_for(name, arguments)
            if mode == "deny":
                state["vetoed"] += 1
                answer("Denied: policy does not allow '{}'.".format(name))
                if spec.get("halt"):
                    self._answer_remaining(memory, calls[idx + 1:], "Error: run halted by policy.")
                    return "vetoed"
                continue
            if self._needs_approval(mode, spec, arguments):
                verdict = self._approved(decision, call_id)
                if verdict is None:
                    memory.suspend(
                        "approval_required",
                        pending={
                            "call_id": call_id, "name": name, "arguments": arguments,
                            "remaining": [c.get("id") for c in calls[idx + 1:]],
                        },
                    )
                    return "suspended"
                if not verdict:
                    state["vetoed"] += 1
                    answer("Denied: approver rejected '{}'.".format(name))
                    continue

            if self._over_budget(state, "max_tool_calls", "tool_calls", extra=0):
                self._answer_remaining(memory, calls[idx:], "Error: tool budget exhausted.")
                return "budget_exhausted"

            result = self._execute_tool(
                name, arguments,
                context={"call_id": call_id, "memory": memory, "agent": self},
            )
            state["tool_calls"] += 1
            text = result if isinstance(result, str) else json.dumps(result, default=str)
            answer(text)
        return None

    def _finish(self, memory, status, state):
        """Record status and outcome on MEMORY and return it."""
        status = status or "error"
        outcome = dict(state)
        outcome["status"] = status
        outcome["iterations"] = self.iteration_count
        outcome["ok"] = status == "final"
        memory.set_var("{}_status".format(self.name), status,
                       desc="Run status for agent: {}".format(self.name))
        memory.set_var("{}_outcome".format(self.name), outcome,
                       desc="Structured outcome for agent: {}".format(self.name))
        return memory

    def __str__(self):
        """Return a concise string representation."""
        return "AGENT({}, tools={})".format(self.name, len(self.tools))

    def __repr__(self):
        """Return a detailed string representation."""
        tool_names = [t.name for t in self.tools]
        return "AGENT(name='{}', tools={}, max_iterations={})".format(
            self.name, tool_names, self.max_iterations
        )


def tool_loop(
    memory,
    llm,
    tools,
    system_prompt="You are a helpful assistant.",
    policy=None,
    budget=None,
    allow=None,
    checkpoint=None,
    decision=None,
    name="agent",
    max_iterations=10,
):
    """
    Run a governed, write-ahead tool loop in one call.

    A thin helper over ``AGENT``: build an agent with the given governance
    options and run it on ``memory``. Pass ``decision={"approve": True}`` with a
    rehydrated MEMORY to resume a run that suspended for approval.

    Returns:
        MEMORY: The updated memory; read ``{name}_status`` and ``{name}_outcome``.
    """
    agent = AGENT(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        name=name,
        allow=allow,
        policy=policy,
        budget=budget,
        checkpoint=checkpoint,
        protocol="native",
    )
    return agent(memory, decision=decision)

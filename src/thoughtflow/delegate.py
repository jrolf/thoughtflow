"""
DELEGATE class for ThoughtFlow.

DELEGATE coordinates work between multiple agents. It supports three
delegation modes:

- **Handoff:** Transfers control entirely to another agent. The first agent
  does not wait for or process the result. One-way.
- **Dispatch:** Sends a task to another agent and waits for its result, which
  is then available to the original agent. Round-trip.
- **Broadcast:** Sends the same task to multiple agents in parallel (or
  sequentially) and collects all results.

DELEGATE itself is not an agent — it is a coordination primitive that agents
use to communicate with other agents.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from thoughtflow._util import event_stamp


def _sum_usage_dicts(usages):
    """Aggregate a sequence of normalized usage dicts into one summary dict (or None)."""
    valid = [u for u in usages if isinstance(u, dict) and u]
    if not valid:
        return None
    totals = {"prompt_tokens": 0, "completion_tokens": 0}
    total_cost = 0.0
    saw_cost = False
    for u in valid:
        totals["prompt_tokens"] += int(u.get("prompt_tokens", u.get("input_tokens", 0)) or 0)
        totals["completion_tokens"] += int(
            u.get("completion_tokens", u.get("output_tokens", 0)) or 0
        )
        if u.get("cost") is not None:
            total_cost += float(u["cost"])
            saw_cost = True
    totals["total_tokens"] = totals["prompt_tokens"] + totals["completion_tokens"]
    if saw_cost:
        totals["cost"] = total_cost
    return totals


class DELEGATE:
    """
    Multi-agent coordination primitive.

    DELEGATE enables agents and cognitive callables to work together by routing
    tasks between them:

    - ``'handoff'``: Fire-and-forget. The receiving agent gets a copy of memory
      and runs independently.
    - ``'dispatch'``: Request-response. The receiving agent processes the task
      and its result + structured outcome (and optionally variables/messages)
      merge back into the caller's memory.
    - ``'dispatch_many'``: Supervisor fan-out assigning distinct tasks to
      multiple specialists sequentially or in parallel.
    - ``'broadcast'``: Fan-out sending the same task to multiple agents
      sequentially or in parallel.

    Attributes:
        name (str): Identifier for this delegation coordinator.
        agents (dict): Name-to-callable mapping of registered specialists.
        id (str): Unique identifier for this DELEGATE instance.
        delegation_log (list): Record of all delegations performed.
    """

    def __init__(self, agents=None, name="delegate"):
        """
        Initialize a DELEGATE with a list or dict of agents/callables.

        Args:
            agents (list or dict, optional): Either an iterable of ``AGENT`` /
                ``THOUGHT`` / named callables, or a ``{name: callable}`` dict so
                plain functions and lambdas need no ``.name`` attribute (#41).
            name (str): Identifier for this coordinator.
        """
        self.name = name
        self.id = event_stamp()
        self.delegation_log = []

        self.agents = {}
        if isinstance(agents, dict):
            for agent_name, agent_fn in agents.items():
                self.agents[str(agent_name)] = agent_fn
        elif agents:
            for agent in agents:
                agent_name = (
                    getattr(agent, "name", None)
                    or getattr(agent, "__name__", None)
                    or str(agent)
                )
                self.agents[str(agent_name)] = agent

    def _execute_specialist(self, base_memory, agent_name, task=None, extra_vars=None):
        """
        Run one registered specialist on an isolated memory copy and build a rich outcome (#41).

        Returns:
            tuple: ``(result_memory, outcome_dict)`` where ``outcome_dict`` has
            ``ok``, ``result``, ``error``, ``usage``, and ``messages``.
        """
        agent = self._get_agent(agent_name)
        memory_copy = self._copy_memory(base_memory)

        baseline_msg_count = (
            len(memory_copy.get_msgs()) if hasattr(memory_copy, "get_msgs") else 0
        )
        baseline_usage_count = (
            len(memory_copy.get_emits("usage")) if hasattr(memory_copy, "get_emits") else 0
        )

        if isinstance(extra_vars, dict) and hasattr(memory_copy, "set_var"):
            for k, v in extra_vars.items():
                memory_copy.set_var(k, v)

        if task and hasattr(memory_copy, "add_msg"):
            memory_copy.add_msg("user", task)

        try:
            returned = agent(memory_copy)
        except Exception as exc:
            outcome = {
                "ok": False,
                "result": None,
                "error": str(exc),
                "usage": None,
                "messages": [],
            }
            return memory_copy, outcome

        # Support both MEMORY-returning primitives and plain callables returning a value directly
        is_mem_like = hasattr(returned, "get_var") and callable(getattr(returned, "get_var", None))
        result_memory = returned if is_mem_like else memory_copy

        if not is_mem_like:
            direct_ok = True
            direct_err = None
            direct_usage = None
            direct_res = returned
            if isinstance(returned, dict) and "ok" in returned and ("result" in returned or "error" in returned):
                direct_ok = bool(returned.get("ok"))
                direct_res = returned.get("result")
                direct_err = returned.get("error")
                direct_usage = returned.get("usage")
            outcome = {
                "ok": direct_ok,
                "result": direct_res,
                "error": direct_err,
                "usage": direct_usage,
                "messages": [],
            }
            return result_memory, outcome

        intrinsic_name = getattr(agent, "name", None)
        candidate_result_keys = ["{}_result".format(agent_name)]
        if getattr(agent, "output_var", None):
            candidate_result_keys.append(agent.output_var)
        if intrinsic_name and intrinsic_name != agent_name:
            candidate_result_keys.append("{}_result".format(intrinsic_name))

        result = None
        for rkey in candidate_result_keys:
            val = result_memory.get_var(rkey)
            if val is not None:
                result = val
                break

        step_outcome = result_memory.get_var("{}_outcome".format(agent_name))
        if step_outcome is None and intrinsic_name and intrinsic_name != agent_name:
            step_outcome = result_memory.get_var("{}_outcome".format(intrinsic_name))

        last_err_var = result_memory.get_var("{}_last_error".format(agent_name))
        if last_err_var is None and intrinsic_name and intrinsic_name != agent_name:
            last_err_var = result_memory.get_var("{}_last_error".format(intrinsic_name))

        ok = True
        error = None
        usage = None
        if isinstance(step_outcome, dict):
            if "ok" in step_outcome:
                ok = bool(step_outcome["ok"])
            elif step_outcome.get("status") in ("error", "failed", "aborted"):
                ok = False
            error = step_outcome.get("error")
            usage = step_outcome.get("usage")
        elif isinstance(last_err_var, dict) and result is None:
            ok = False
            error = last_err_var.get("reason")

        if usage is None and hasattr(result_memory, "get_emits"):
            new_emits = result_memory.get_emits("usage")[baseline_usage_count:]
            usage = _sum_usage_dicts([e.get("payload") for e in new_emits])

        new_messages = []
        if hasattr(result_memory, "get_msgs"):
            all_msgs = result_memory.get_msgs()
            raw_new = all_msgs[baseline_msg_count:]
            # Skip the synthetic task user message we injected on entry when task was provided
            if task and raw_new and raw_new[0].get("role") == "user" and raw_new[0].get("content") == task:
                raw_new = raw_new[1:]
            new_messages = [
                {"role": m.get("role", "assistant"), "content": m.get("content", "")}
                for m in raw_new
            ]

        outcome = {
            "ok": ok,
            "result": result,
            "error": error,
            "usage": usage,
            "messages": new_messages,
        }
        return result_memory, outcome

    def handoff(self, memory, agent_name, task=None):
        """
        Hand off control to another agent without expecting a result.

        The receiving agent gets a copy of the memory (not the original) so
        the caller's state is not affected.
        """
        result_memory, outcome = self._execute_specialist(memory, agent_name, task=task)
        self._log("handoff", agent_name, task, result=outcome["result"])
        return result_memory

    def dispatch(
        self,
        memory,
        agent_name,
        task=None,
        merge_vars=False,
        merge_msgs=False,
    ):
        """
        Dispatch a task to another agent and merge its result and outcome back (#41).

        Writes ``{agent_name}_dispatch_result`` (backward-compatible raw result)
        and ``{agent_name}_dispatch_outcome`` (``{"ok", "result", "error", "usage", "messages"}``),
        with optional variable and transcript merge-back.

        Args:
            memory: Caller ``MEMORY`` instance (modified in place).
            agent_name (str): Registered specialist name.
            task (str, optional): Task instruction added to the specialist copy.
            merge_vars (bool or list[str]): Copy all new/changed specialist
                variables (``True``) or an explicit list of variable keys back
                onto ``memory``.
            merge_msgs (bool): When ``True``, append the specialist's new
                conversation turns onto ``memory``.

        Returns:
            MEMORY: Updated ``memory``.
        """
        baseline_vars = (
            memory.get_all_vars(resolve_refs=False)
            if (merge_vars and hasattr(memory, "get_all_vars"))
            else {}
        )
        result_memory, outcome = self._execute_specialist(memory, agent_name, task=task)
        result = outcome["result"]

        if hasattr(memory, "set_var"):
            memory.set_var(
                "{}_dispatch_result".format(agent_name),
                result,
                desc="Dispatch result from agent: {}".format(agent_name),
            )
            memory.set_var(
                "{}_dispatch_outcome".format(agent_name),
                dict(outcome),
                desc="Structured dispatch outcome from agent: {}".format(agent_name),
            )

        if merge_vars and hasattr(result_memory, "get_all_vars") and hasattr(memory, "set_var"):
            spec_vars = result_memory.get_all_vars()
            keys_to_merge = (
                list(merge_vars)
                if isinstance(merge_vars, (list, tuple, set))
                else [k for k, v in spec_vars.items() if baseline_vars.get(k) != v]
            )
            for key in keys_to_merge:
                if key in spec_vars:
                    memory.set_var(key, spec_vars[key])

        if merge_msgs and hasattr(memory, "add_msg"):
            for msg in outcome["messages"]:
                memory.add_msg(msg["role"], msg["content"])

        self._log("dispatch", agent_name, task, result=result)
        return memory

    def dispatch_many(self, memory, assignments, parallel=False, max_workers=None):
        """
        Dispatch distinct tasks to multiple specialists sequentially or in parallel (#45).

        Args:
            memory: Caller ``MEMORY`` instance.
            assignments (list): Sequence of ``{"agent": name, "task": ..., "vars": {...}}``
                dicts (or ``(agent_name, task)`` tuples).
            parallel (bool): Execute assignments concurrently via ``ThreadPoolExecutor``
                when ``True`` (default ``False``).
            max_workers (int, optional): Worker limit when ``parallel=True``.

        Returns:
            list[dict]: Ordered per-assignment reports containing ``agent``,
            ``task``, ``ok``, ``result``, ``error``, ``usage``, and ``messages``.
        """
        normalized = []
        for entry in assignments or []:
            if isinstance(entry, dict):
                normalized.append({
                    "agent": entry["agent"],
                    "task": entry.get("task"),
                    "vars": entry.get("vars"),
                })
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                normalized.append({"agent": entry[0], "task": entry[1], "vars": None})
            else:
                raise ValueError("Invalid dispatch_many assignment: {!r}".format(entry))

        def _run_assignment(spec):
            agent_name = spec["agent"]
            task_text = spec["task"]
            if agent_name not in self.agents:
                return {
                    "agent": agent_name,
                    "task": task_text,
                    "ok": False,
                    "result": None,
                    "error": "Agent '{}' not registered with DELEGATE '{}'.".format(
                        agent_name, self.name
                    ),
                    "usage": None,
                    "messages": [],
                }
            _, out = self._execute_specialist(
                memory, agent_name, task=task_text, extra_vars=spec["vars"]
            )
            report = {"agent": agent_name, "task": task_text}
            report.update(out)
            return report

        if parallel and len(normalized) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_run_assignment, spec) for spec in normalized]
                reports = [f.result() for f in futures]
        else:
            reports = [_run_assignment(spec) for spec in normalized]

        if hasattr(memory, "set_var"):
            for rep in reports:
                aname = rep["agent"]
                memory.set_var(
                    "{}_dispatch_result".format(aname),
                    rep["result"],
                    desc="Dispatch result from agent: {}".format(aname),
                )
                memory.set_var(
                    "{}_dispatch_outcome".format(aname),
                    {k: rep[k] for k in ("ok", "result", "error", "usage", "messages")},
                    desc="Structured dispatch outcome from agent: {}".format(aname),
                )
            memory.set_var(
                "{}_dispatch_many_outcomes".format(self.name),
                list(reports),
                desc="Ordered dispatch_many outcomes for {}".format(self.name),
            )

        self._log("dispatch_many", [r["agent"] for r in reports], task=None, result=reports)
        return reports

    def broadcast(
        self,
        memory,
        task=None,
        agent_names=None,
        parallel=False,
        max_workers=None,
    ):
        """
        Send the same task to multiple agents and collect results and outcomes (#41, #45).

        Stores ``{self.name}_broadcast_results`` (backward-compatible ``{agent: result}``)
        and ``{self.name}_broadcast_outcomes`` (``{agent: {"ok", "result", "error", "usage", "messages"}}``).
        """
        targets = list(agent_names) if agent_names is not None else list(self.agents.keys())

        def _run_target(agent_name):
            if agent_name not in self.agents:
                err_text = "Error: Agent '{}' not found.".format(agent_name)
                return agent_name, err_text, {
                    "ok": False,
                    "result": None,
                    "error": err_text,
                    "usage": None,
                    "messages": [],
                }
            _, out = self._execute_specialist(memory, agent_name, task=task)
            return agent_name, out["result"], out

        if parallel and len(targets) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_run_target, name) for name in targets]
                pairs = [f.result() for f in futures]
        else:
            pairs = [_run_target(name) for name in targets]

        results = {}
        outcomes = {}
        for agent_name, raw_res, out_dict in pairs:
            results[agent_name] = raw_res
            outcomes[agent_name] = out_dict

        if hasattr(memory, "set_var"):
            memory.set_var(
                "{}_broadcast_results".format(self.name),
                results,
                desc="Broadcast results from {} agents".format(len(results)),
            )
            memory.set_var(
                "{}_broadcast_outcomes".format(self.name),
                outcomes,
                desc="Structured broadcast outcomes from {} agents".format(len(outcomes)),
            )

        self._log("broadcast", targets, task, result=results)
        return memory

    def _get_agent(self, agent_name):
        """
        Look up an agent by name.

        Args:
            agent_name (str): The agent name to look up.

        Returns:
            The agent instance.

        Raises:
            KeyError: If the agent is not registered.
        """
        if agent_name not in self.agents:
            raise KeyError("Agent '{}' not registered with DELEGATE '{}'.".format(
                agent_name, self.name
            ))
        return self.agents[agent_name]

    def _copy_memory(self, memory):
        """
        Create a working copy of memory for delegation.

        Uses memory's copy() method if available so variable values, history,
        descriptions, tombstones, and channels survive faithfully; otherwise
        creates a new MEMORY and transfers messages and current variable values.

        Args:
            memory: The MEMORY instance to copy.

        Returns:
            A new MEMORY instance with the same state.
        """
        if hasattr(memory, "copy") and callable(getattr(memory, "copy", None)):
            return memory.copy()

        from thoughtflow.memory import MEMORY
        new_memory = MEMORY()

        if hasattr(memory, "get_msgs"):
            for msg in memory.get_msgs():
                role = msg.get("role", "user")
                content = msg.get("content", "")
                channel = msg.get("channel", "unknown")
                new_memory.add_msg(role, content, channel=channel)

        if hasattr(memory, "get_all_vars") and callable(getattr(memory, "get_all_vars", None)):
            for key, value in memory.get_all_vars().items():
                desc = memory.get_var_desc(key) if hasattr(memory, "get_var_desc") else None
                new_memory.set_var(key, value, desc=desc)
        elif hasattr(memory, "vars") and isinstance(memory.vars, dict):
            for key, value in memory.vars.items():
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    current = memory.get_var(key)
                    if current is not None:
                        new_memory.set_var(key, current)
                else:
                    new_memory.set_var(key, value)

        return new_memory

    def _log(self, mode, target, task=None, result=None):
        """
        Record a delegation event.

        Args:
            mode (str): The delegation mode ('handoff', 'dispatch', 'broadcast').
            target: The target agent(s).
            task (str, optional): The task text.
            result: The result, if any.
        """
        self.delegation_log.append({
            "stamp": event_stamp(),
            "mode": mode,
            "target": target,
            "task": task,
            "has_result": result is not None,
        })

    def __str__(self):
        """Return a concise string representation."""
        return "DELEGATE({}, agents={})".format(self.name, list(self.agents.keys()))

    def __repr__(self):
        """Return a detailed string representation."""
        return "DELEGATE(name='{}', agents={}, delegations={})".format(
            self.name, list(self.agents.keys()), len(self.delegation_log)
        )


def map_thought(
    thought,
    memory,
    items=None,
    n=None,
    var_name="item",
    parallel=True,
    max_workers=None,
):
    """
    Fan out a ``THOUGHT`` (or ``DECIDE`` / ``PLAN`` / ``memory -> memory`` callable)
    across isolated ``MEMORY`` copies, optionally in parallel (#45).

    Supports both self-consistency / voting (``n=5``) and data-parallel mapping
    (``items=[...]`` with ``var_name='item'`` or ``var_name=None`` to unpack item
    dicts directly onto each memory copy). Clones ``thought.copy()`` per branch
    when available so ``last_result`` and ``last_outcome`` never race across
    worker threads.

    Args:
        thought: ``THOUGHT``, ``DECIDE``, ``PLAN``, or callable ``fn(memory)``.
        memory (MEMORY): Base ``MEMORY`` cloned per branch (never mutated).
        items (iterable, optional): Input items mapped across branches.
        n (int, optional): Number of repeated runs when ``items`` is ``None``.
        var_name (str or None): Variable name seeded on each memory copy when
            ``items`` is provided (default ``'item'``). Pass ``None`` when each
            item is a ``dict`` of variables to unpack directly.
        parallel (bool): Execute branches via ``ThreadPoolExecutor`` when
            ``True`` (default ``True``).
        max_workers (int, optional): Maximum worker threads when ``parallel=True``.

    Returns:
        list[dict]: Ordered list of per-branch outcome dicts (``index``, ``ok``,
        ``result``, ``error``, ``usage``, ``attempts``, plus ``item`` when
        ``items`` was supplied).

    Example:
        >>> outcomes = map_thought(voter, memory, n=5, parallel=True)
        >>> answers = [o["result"] for o in outcomes if o["ok"]]
    """
    from thoughtflow.memory import MEMORY

    if items is not None:
        work_items = list(items)
        has_items = True
    elif n is not None:
        count = int(n)
        if count < 0:
            raise ValueError("'n' must be >= 0, got {}".format(n))
        work_items = [None] * count
        has_items = False
    else:
        raise ValueError("map_thought requires either 'items' or 'n'")

    if not work_items:
        return []

    def _clone_mem():
        if memory is None:
            return MEMORY()
        if hasattr(memory, "copy") and callable(getattr(memory, "copy", None)):
            return memory.copy()
        fresh = MEMORY()
        if hasattr(memory, "get_all_vars"):
            for k, v in memory.get_all_vars().items():
                fresh.set_var(k, v)
        return fresh

    def _run_branch(idx, item):
        mem_copy = _clone_mem()
        if has_items:
            if var_name is None and isinstance(item, dict):
                for k, v in item.items():
                    mem_copy.set_var(k, v)
            else:
                mem_copy.set_var(var_name, item)

        branch_step = (
            thought.copy()
            if hasattr(thought, "copy") and callable(getattr(thought, "copy", None))
            else thought
        )

        try:
            returned = branch_step(mem_copy)
        except Exception as exc:
            out = {
                "index": idx,
                "ok": False,
                "result": None,
                "error": str(exc),
                "usage": None,
                "attempts": 1,
            }
            if has_items:
                out["item"] = item
            return out

        is_mem = hasattr(returned, "get_var") and callable(getattr(returned, "get_var", None))
        out_var = getattr(branch_step, "output_var", None)
        step_name = getattr(branch_step, "name", None)
        if is_mem:
            if out_var:
                res_val = returned.get_var(out_var)
            elif step_name:
                res_val = returned.get_var("{}_result".format(step_name))
            else:
                res_val = getattr(branch_step, "last_result", None)
            outcome_var = (
                returned.get_var("{}_outcome".format(step_name)) if step_name else None
            )
        else:
            res_val = returned
            outcome_var = None

        base_outcome = dict(
            outcome_var
            if isinstance(outcome_var, dict)
            else (getattr(branch_step, "last_outcome", None) or {})
        )
        branch_outcome = dict(base_outcome)
        branch_outcome.update({
            "index": idx,
            "ok": bool(base_outcome.get("ok", True)),
            "result": res_val,
            "error": base_outcome.get("error"),
            "usage": base_outcome.get("usage"),
            "attempts": int(base_outcome.get("attempts", 1)),
        })
        if has_items:
            branch_outcome["item"] = item
        return branch_outcome

    if parallel and len(work_items) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_run_branch, i, it) for i, it in enumerate(work_items)]
            return [f.result() for f in futures]

    return [_run_branch(i, it) for i, it in enumerate(work_items)]


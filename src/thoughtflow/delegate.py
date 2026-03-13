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

from thoughtflow._util import event_stamp


class DELEGATE:
    """
    Multi-agent coordination primitive.

    DELEGATE enables agents to work together by routing tasks between them.
    Each delegation has a mode that determines the communication pattern:

    - 'handoff': Fire-and-forget. The receiving agent gets a copy of memory
      and runs independently. The caller does not wait.
    - 'dispatch': Request-response. The receiving agent processes the task
      and its result is merged back into the caller's memory.
    - 'broadcast': Fan-out. Multiple agents receive the same task and their
      results are collected.

    Attributes:
        name (str): Identifier for this delegation coordinator.
        agents (dict): Name-to-agent mapping of available agents.
        id (str): Unique identifier for this DELEGATE instance.
        delegation_log (list): Record of all delegations performed.

    Example:
        >>> researcher = AGENT(llm=llm, tools=[search], name="researcher")
        >>> writer = AGENT(llm=llm, name="writer")
        >>> delegate = DELEGATE(agents=[researcher, writer])
        >>>
        >>> # Dispatch: send to researcher, get result back
        >>> memory = delegate.dispatch(memory, "researcher", "Find info on X")
        >>>
        >>> # Handoff: pass to writer, don't wait
        >>> delegate.handoff(memory, "writer", "Write a summary")
        >>>
        >>> # Broadcast: ask both agents the same question
        >>> results = delegate.broadcast(memory, "Summarize your findings")
    """

    def __init__(self, agents=None, name="delegate"):
        """
        Initialize a DELEGATE with a set of agents.

        Args:
            agents (list, optional): List of AGENT instances (or any callable
                that accepts memory and returns memory). Each must have a
                'name' attribute.
            name (str): Identifier for this coordinator.
        """
        self.name = name
        self.id = event_stamp()
        self.delegation_log = []

        # Build name -> agent lookup
        agent_list = agents or []
        self.agents = {}
        for agent in agent_list:
            agent_name = getattr(agent, 'name', str(agent))
            self.agents[agent_name] = agent

    def handoff(self, memory, agent_name, task=None):
        """
        Hand off control to another agent without expecting a result.

        The receiving agent gets a copy of the memory (not the original) so
        the caller's state is not affected. This is a one-way delegation
        where the calling agent continues its own work immediately.

        Args:
            memory: The MEMORY instance to copy for the receiving agent.
            agent_name (str): Name of the agent to hand off to.
            task (str, optional): Additional task instruction. If provided,
                it is added as a user message to the copy before handoff.

        Returns:
            MEMORY: A new memory instance representing the handed-off state.
                The original memory is unchanged.

        Raises:
            KeyError: If the agent_name is not registered.

        Example:
            >>> delegate.handoff(memory, "writer", "Write a summary of the research.")
        """
        agent = self._get_agent(agent_name)

        # Copy memory so the original is not mutated
        memory_copy = self._copy_memory(memory)

        if task and hasattr(memory_copy, "add_msg"):
            memory_copy.add_msg("user", task)

        result_memory = agent(memory_copy)

        self._log("handoff", agent_name, task)
        return result_memory

    def dispatch(self, memory, agent_name, task=None):
        """
        Dispatch a task to another agent and merge the result back.

        The receiving agent processes the task using a copy of memory. The
        result (stored in the agent's result variable) is then injected back
        into the original memory so the calling agent can use it.

        Args:
            memory: The MEMORY instance. Modified in place with the result.
            agent_name (str): Name of the agent to dispatch to.
            task (str, optional): Additional task instruction.

        Returns:
            MEMORY: The original memory, updated with the dispatched agent's
                result stored in a variable named '{agent_name}_dispatch_result'.

        Raises:
            KeyError: If the agent_name is not registered.

        Example:
            >>> memory = delegate.dispatch(memory, "researcher", "Find info on X")
            >>> result = memory.get_var("researcher_dispatch_result")
        """
        agent = self._get_agent(agent_name)

        # Copy memory for the agent to work on
        memory_copy = self._copy_memory(memory)

        if task and hasattr(memory_copy, "add_msg"):
            memory_copy.add_msg("user", task)

        result_memory = agent(memory_copy)

        # Extract the result from the agent's memory
        result_key = "{}_result".format(agent_name)
        result = None
        if hasattr(result_memory, "get_var"):
            result = result_memory.get_var(result_key)

        # Merge the result back into the original memory
        dispatch_key = "{}_dispatch_result".format(agent_name)
        if hasattr(memory, "set_var"):
            memory.set_var(
                dispatch_key, result,
                desc="Dispatch result from agent: {}".format(agent_name)
            )

        self._log("dispatch", agent_name, task, result=result)
        return memory

    def broadcast(self, memory, task=None, agent_names=None):
        """
        Send the same task to multiple agents and collect all results.

        Each agent receives a copy of memory (plus the optional task) and
        runs independently. Results are collected into a dict keyed by
        agent name and stored in the original memory.

        Args:
            memory: The MEMORY instance.
            task (str, optional): Task instruction for all agents.
            agent_names (list[str], optional): Specific agents to broadcast to.
                If None, broadcasts to all registered agents.

        Returns:
            MEMORY: The original memory, updated with a variable named
                '{self.name}_broadcast_results' containing a dict of
                {agent_name: result}.

        Example:
            >>> memory = delegate.broadcast(memory, "Summarize your findings")
            >>> results = memory.get_var("delegate_broadcast_results")
        """
        targets = agent_names or list(self.agents.keys())
        results = {}

        for agent_name in targets:
            if agent_name not in self.agents:
                results[agent_name] = "Error: Agent '{}' not found.".format(agent_name)
                continue

            agent = self.agents[agent_name]
            memory_copy = self._copy_memory(memory)

            if task and hasattr(memory_copy, "add_msg"):
                memory_copy.add_msg("user", task)

            result_memory = agent(memory_copy)

            # Extract result
            result_key = "{}_result".format(agent_name)
            result = None
            if hasattr(result_memory, "get_var"):
                result = result_memory.get_var(result_key)
            results[agent_name] = result

        # Store broadcast results in original memory
        broadcast_key = "{}_broadcast_results".format(self.name)
        if hasattr(memory, "set_var"):
            memory.set_var(
                broadcast_key, results,
                desc="Broadcast results from {} agents".format(len(results))
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

        Uses memory's copy() method if available; otherwise creates a new
        MEMORY and transfers messages and variables.

        Args:
            memory: The MEMORY instance to copy.

        Returns:
            A new MEMORY instance with the same state.
        """
        from thoughtflow.memory import MEMORY
        new_memory = MEMORY()

        if hasattr(memory, "get_msgs"):
            for msg in memory.get_msgs():
                role = msg.get("role", "user")
                content = msg.get("content", "")
                new_memory.add_msg(role, content)

        # Copy variables
        if hasattr(memory, "vars") and isinstance(memory.vars, dict):
            for key, value in memory.vars.items():
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

"""
Core Agent contract for ThoughtFlow.

The Agent is the fundamental primitive - something that can be called
with messages and parameters. Everything else is composition.

Example:
    >>> adapter = OpenAIAdapter(api_key="...")
    >>> agent = Agent(adapter)
    >>> response = agent.call([{"role": "user", "content": "Hello"}])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from thoughtflow.adapters.base import Adapter
    from thoughtflow.message import MessageList
    from thoughtflow.trace.session import Session


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol defining the Agent contract.

    Any object implementing `call(msg_list, params)` is an Agent.
    """

    def call(
        self,
        msg_list: MessageList,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Call the agent with a message list.

        Args:
            msg_list: List of messages in the conversation.
            params: Optional parameters (temperature, max_tokens, etc.)

        Returns:
            The agent's response as a string.
        """
        ...


class Agent:
    """Base Agent implementation.

    An Agent wraps an adapter and provides a simple `call` interface.
    This is the core primitive of ThoughtFlow - explicit, composable, testable.

    Attributes:
        adapter: The provider adapter to use for completions.

    Example:
        >>> from thoughtflow import Agent
        >>> from thoughtflow.adapters import OpenAIAdapter
        >>>
        >>> agent = Agent(OpenAIAdapter(api_key="..."))
        >>> response = agent.call([
        ...     {"role": "system", "content": "You are helpful."},
        ...     {"role": "user", "content": "Hello!"}
        ... ])
    """

    def __init__(self, adapter: Adapter) -> None:
        """Initialize the Agent with an adapter.

        Args:
            adapter: The provider adapter for making LLM calls.
        """
        self.adapter = adapter

    def call(
        self,
        msg_list: MessageList,
        params: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> str:
        """Call the agent with a message list.

        Args:
            msg_list: List of message dicts with 'role' and 'content' keys.
            params: Optional parameters (temperature, max_tokens, seed, etc.)
            session: Optional Session for tracing the call.

        Returns:
            The model's response as a string.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement actual adapter call
        # TODO: Add session tracing
        raise NotImplementedError(
            "Agent.call() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )


class TracedAgent:
    """Agent wrapper that automatically traces all calls.

    Wraps any Agent and records inputs, outputs, timing, and metadata
    to a Session object for debugging, evaluation, and replay.

    Example:
        >>> from thoughtflow.trace import Session
        >>> session = Session()
        >>> traced = TracedAgent(agent, session)
        >>> response = traced.call(messages)
        >>> print(session.events)  # See all recorded events
    """

    def __init__(self, agent: Agent, session: Session) -> None:
        """Initialize TracedAgent.

        Args:
            agent: The underlying agent to wrap.
            session: The session to record traces to.
        """
        self.agent = agent
        self.session = session

    def call(
        self,
        msg_list: MessageList,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Call the agent and trace the execution.

        Args:
            msg_list: List of messages.
            params: Optional parameters.

        Returns:
            The agent's response.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement tracing wrapper
        raise NotImplementedError(
            "TracedAgent.call() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )

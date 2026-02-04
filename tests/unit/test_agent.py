"""
Unit tests for the Agent module.
"""

from __future__ import annotations

import pytest

from thoughtflow.agent import Agent, AgentProtocol, TracedAgent


class TestAgentProtocol:
    """Tests for the AgentProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """AgentProtocol should be usable with isinstance()."""

        class CustomAgent:
            def call(self, msg_list, params=None):
                return "response"

        agent = CustomAgent()
        assert isinstance(agent, AgentProtocol)

    def test_non_conforming_object_fails_protocol(self) -> None:
        """Objects without call() should not match the protocol."""

        class NotAnAgent:
            def process(self, msg_list):
                return "response"

        not_agent = NotAnAgent()
        assert not isinstance(not_agent, AgentProtocol)


class TestAgent:
    """Tests for the Agent class."""

    def test_agent_requires_adapter(self, mock_adapter) -> None:
        """Agent should be initialized with an adapter."""
        agent = Agent(mock_adapter)
        assert agent.adapter is mock_adapter

    def test_agent_call_raises_not_implemented(
        self, mock_adapter, sample_messages
    ) -> None:
        """Agent.call() should raise NotImplementedError (placeholder)."""
        agent = Agent(mock_adapter)

        with pytest.raises(NotImplementedError) as exc_info:
            agent.call(sample_messages)

        assert "placeholder" in str(exc_info.value).lower()


class TestTracedAgent:
    """Tests for the TracedAgent wrapper."""

    def test_traced_agent_wraps_agent(self, mock_adapter) -> None:
        """TracedAgent should wrap an Agent and Session."""
        from thoughtflow.trace import Session

        agent = Agent(mock_adapter)
        session = Session()

        traced = TracedAgent(agent, session)

        assert traced.agent is agent
        assert traced.session is session

    def test_traced_agent_call_raises_not_implemented(
        self, mock_adapter, sample_messages
    ) -> None:
        """TracedAgent.call() should raise NotImplementedError (placeholder)."""
        from thoughtflow.trace import Session

        agent = Agent(mock_adapter)
        session = Session()
        traced = TracedAgent(agent, session)

        with pytest.raises(NotImplementedError) as exc_info:
            traced.call(sample_messages)

        assert "placeholder" in str(exc_info.value).lower()

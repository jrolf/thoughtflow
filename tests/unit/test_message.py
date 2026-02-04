"""
Unit tests for the Message module.
"""

from __future__ import annotations

import pytest

from thoughtflow.message import Message, normalize_messages


class TestMessage:
    """Tests for the Message dataclass."""

    def test_create_message(self) -> None:
        """Should create a message with role and content."""
        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_message_to_dict(self) -> None:
        """Should convert message to dict."""
        msg = Message(role="user", content="Hello!")
        d = msg.to_dict()

        assert d == {"role": "user", "content": "Hello!"}

    def test_message_to_dict_with_name(self) -> None:
        """Should include name in dict if set."""
        msg = Message(role="user", content="Hello!", name="Alice")
        d = msg.to_dict()

        assert d == {"role": "user", "content": "Hello!", "name": "Alice"}

    def test_message_to_dict_with_tool_call_id(self) -> None:
        """Should include tool_call_id in dict if set."""
        msg = Message(role="tool", content="Result", tool_call_id="call_123")
        d = msg.to_dict()

        assert d == {"role": "tool", "content": "Result", "tool_call_id": "call_123"}

    def test_message_from_dict(self) -> None:
        """Should create message from dict."""
        d = {"role": "assistant", "content": "Hi there!"}
        msg = Message.from_dict(d)

        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_message_from_dict_with_optional_fields(self) -> None:
        """Should handle optional fields when creating from dict."""
        d = {
            "role": "user",
            "content": "Hello",
            "name": "Bob",
            "metadata": {"source": "test"},
        }
        msg = Message.from_dict(d)

        assert msg.name == "Bob"
        assert msg.metadata == {"source": "test"}


class TestMessageFactoryMethods:
    """Tests for Message factory methods."""

    def test_system_message(self) -> None:
        """Message.system() should create a system message."""
        msg = Message.system("You are helpful.")
        assert msg.role == "system"
        assert msg.content == "You are helpful."

    def test_user_message(self) -> None:
        """Message.user() should create a user message."""
        msg = Message.user("Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_assistant_message(self) -> None:
        """Message.assistant() should create an assistant message."""
        msg = Message.assistant("Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"


class TestNormalizeMessages:
    """Tests for the normalize_messages function."""

    def test_normalize_dicts(self) -> None:
        """Should pass through dicts unchanged."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = normalize_messages(messages)

        assert result == messages

    def test_normalize_message_objects(self) -> None:
        """Should convert Message objects to dicts."""
        messages = [
            Message.user("Hello"),
            Message.assistant("Hi"),
        ]
        result = normalize_messages(messages)

        assert result == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

    def test_normalize_mixed(self) -> None:
        """Should handle mixed Message objects and dicts."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            Message.user("Hello"),
            {"role": "assistant", "content": "Hi"},
        ]
        result = normalize_messages(messages)

        assert len(result) == 3
        assert all(isinstance(m, dict) for m in result)

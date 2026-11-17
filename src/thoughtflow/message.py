"""
Message schema for ThoughtFlow.

Messages are the universal currency across providers. ThoughtFlow keeps
messages provider-agnostic, minimal, and stable.

Typical structure:
    msg_list = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Plain aliases (no TypeAlias — added in Python 3.10; we support 3.9+).
Role = Literal["system", "user", "assistant", "tool"]
MessageDict = dict[str, Any]
MessageList = list[MessageDict]


@dataclass
class Message:
    """A single message in a conversation.

    This is an optional structured representation. You can also use
    plain dicts - ThoughtFlow accepts both.

    Attributes:
        role: The role of the message sender (system, user, assistant, tool).
        content: The text content of the message.
        name: Optional name for the sender (useful for multi-agent scenarios).
        tool_calls: Optional list of structured tool-call dicts (for assistant messages).
        tool_call_id: Optional ID linking to a tool call (for tool responses).
        metadata: Optional metadata dict for extensions.

    Example:
        >>> msg = Message(role="user", content="Hello!")
        >>> msg.to_dict()
        {'role': 'user', 'content': 'Hello!'}
    """

    role: Role
    content: str = ""
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> MessageDict:
        """Convert to a provider-compatible dict.

        Returns:
            Dict with role, content, and optional fields.
        """
        result: MessageDict = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = list(self.tool_calls)
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result

    @classmethod
    def from_dict(cls, data: MessageDict) -> Message:
        """Create a Message from a dict.

        Args:
            data: Dict with at least 'role' key.

        Returns:
            A Message instance.
        """
        return cls(
            role=data["role"],
            content=data.get("content") or "",
            name=data.get("name"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def system(cls, content: str) -> Message:
        """Create a system message.

        Args:
            content: The system prompt content.

        Returns:
            A Message with role='system'.
        """
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        """Create a user message.

        Args:
            content: The user's message content.

        Returns:
            A Message with role='user'.
        """
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls,
        content: str = "",
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Create an assistant message (with optional tool_calls)."""
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str | None = None) -> Message:
        """Create a tool response message linked to ``tool_call_id``."""
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


def normalize_messages(messages: list[Message | MessageDict]) -> MessageList:
    """Normalize a list of messages to dicts.

    Accepts both Message objects and dicts, returning a uniform list of dicts.

    Args:
        messages: List of Message objects or dicts.

    Returns:
        List of message dicts.
    """
    result: MessageList = []
    for msg in messages:
        if isinstance(msg, Message):
            result.append(msg.to_dict())
        else:
            result.append(msg)
    return result

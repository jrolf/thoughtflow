"""
Event types for ThoughtFlow tracing.

Events represent discrete occurrences during an agent run:
- Model calls (start, end, error)
- Tool invocations
- Memory operations
- Custom user events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of events that can occur during a session."""

    # Agent lifecycle
    CALL_START = "call_start"
    CALL_END = "call_end"
    CALL_ERROR = "call_error"

    # Model interactions
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    MODEL_ERROR = "model_error"

    # Tool interactions
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"

    # Memory interactions
    MEMORY_RETRIEVE = "memory_retrieve"
    MEMORY_STORE = "memory_store"

    # Custom
    CUSTOM = "custom"


@dataclass
class Event:
    """A single event in a session trace.

    Events capture everything that happens during an agent run,
    enabling complete visibility and replay capability.

    Attributes:
        event_type: The type of event.
        timestamp: When the event occurred.
        data: Event-specific data.
        duration_ms: Duration in milliseconds (for end events).
        metadata: Additional metadata.

    Example:
        >>> event = Event(
        ...     event_type=EventType.MODEL_REQUEST,
        ...     data={
        ...         "messages": [...],
        ...         "params": {"model": "gpt-4", "temperature": 0.7}
        ...     }
        ... )
    """

    event_type: EventType | str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dict.

        Returns:
            Dict representation of the event.
        """
        return {
            "event_type": (
                self.event_type.value
                if isinstance(self.event_type, EventType)
                else self.event_type
            ),
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create an Event from a dict.

        Args:
            data: Dict with event data.

        Returns:
            Event instance.
        """
        event_type_str = data["event_type"]
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            event_type = event_type_str

        return cls(
            event_type=event_type,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data", {}),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {}),
        )


# Convenience functions for creating common events


def call_start(messages: list[dict], params: dict | None = None) -> Event:
    """Create a CALL_START event.

    Args:
        messages: The input messages.
        params: Call parameters.

    Returns:
        Event instance.
    """
    return Event(
        event_type=EventType.CALL_START,
        data={"messages": messages, "params": params or {}},
    )


def call_end(response: str, tokens: dict | None = None) -> Event:
    """Create a CALL_END event.

    Args:
        response: The agent's response.
        tokens: Token usage information.

    Returns:
        Event instance.
    """
    return Event(
        event_type=EventType.CALL_END,
        data={"response": response, "tokens": tokens or {}},
    )


def tool_call(tool_name: str, payload: dict) -> Event:
    """Create a TOOL_CALL event.

    Args:
        tool_name: Name of the tool being called.
        payload: The tool's input payload.

    Returns:
        Event instance.
    """
    return Event(
        event_type=EventType.TOOL_CALL,
        data={"tool_name": tool_name, "payload": payload},
    )


def tool_result(tool_name: str, result: Any, success: bool = True) -> Event:
    """Create a TOOL_RESULT event.

    Args:
        tool_name: Name of the tool.
        result: The tool's output.
        success: Whether the tool call succeeded.

    Returns:
        Event instance.
    """
    return Event(
        event_type=EventType.TOOL_RESULT,
        data={"tool_name": tool_name, "result": result, "success": success},
    )

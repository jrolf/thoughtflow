"""
Unit tests for the trace module.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from thoughtflow.trace import Event, EventType, Session, TraceSchema
from thoughtflow.trace.events import call_start, call_end, tool_call, tool_result


class TestSession:
    """Tests for the Session class."""

    def test_session_creates_unique_id(self) -> None:
        """Each session should have a unique ID."""
        s1 = Session()
        s2 = Session()

        assert s1.session_id != s2.session_id

    def test_session_has_creation_timestamp(self) -> None:
        """Session should record creation time."""
        before = datetime.now()
        session = Session()
        after = datetime.now()

        assert before <= session.created_at <= after

    def test_session_starts_empty(self) -> None:
        """New session should have no events."""
        session = Session()
        assert len(session.events) == 0

    def test_add_event(self) -> None:
        """Should be able to add events to session."""
        session = Session()
        event = Event(event_type=EventType.CALL_START, data={"test": True})

        session.add_event(event)

        assert len(session.events) == 1
        assert session.events[0] is event

    def test_session_to_dict(self) -> None:
        """Should serialize session to dict."""
        session = Session(metadata={"test": True})
        d = session.to_dict()

        assert "session_id" in d
        assert "created_at" in d
        assert "events" in d
        assert "metadata" in d
        assert d["metadata"] == {"test": True}

    def test_session_summary(self) -> None:
        """Summary should include key metrics."""
        session = Session()
        summary = session.summary()

        assert "session_id" in summary
        assert "event_count" in summary
        assert "total_tokens" in summary


class TestEvent:
    """Tests for the Event class."""

    def test_event_creation(self) -> None:
        """Should create event with type and data."""
        event = Event(
            event_type=EventType.MODEL_REQUEST,
            data={"messages": []},
        )

        assert event.event_type == EventType.MODEL_REQUEST
        assert event.data == {"messages": []}

    def test_event_has_timestamp(self) -> None:
        """Event should have automatic timestamp."""
        before = datetime.now()
        event = Event(event_type=EventType.CALL_START)
        after = datetime.now()

        assert before <= event.timestamp <= after

    def test_event_to_dict(self) -> None:
        """Should serialize event to dict."""
        event = Event(
            event_type=EventType.CALL_END,
            data={"response": "Hello"},
            duration_ms=150,
        )
        d = event.to_dict()

        assert d["event_type"] == "call_end"
        assert d["data"] == {"response": "Hello"}
        assert d["duration_ms"] == 150

    def test_event_from_dict(self) -> None:
        """Should deserialize event from dict."""
        d = {
            "event_type": "call_start",
            "timestamp": "2025-01-01T12:00:00",
            "data": {"messages": []},
            "duration_ms": None,
            "metadata": {},
        }
        event = Event.from_dict(d)

        assert event.event_type == EventType.CALL_START
        assert event.data == {"messages": []}


class TestEventFactoryFunctions:
    """Tests for event factory functions."""

    def test_call_start_event(self) -> None:
        """call_start() should create CALL_START event."""
        messages = [{"role": "user", "content": "Hi"}]
        event = call_start(messages, params={"temperature": 0.7})

        assert event.event_type == EventType.CALL_START
        assert event.data["messages"] == messages
        assert event.data["params"] == {"temperature": 0.7}

    def test_call_end_event(self) -> None:
        """call_end() should create CALL_END event."""
        event = call_end("Hello!", tokens={"total": 10})

        assert event.event_type == EventType.CALL_END
        assert event.data["response"] == "Hello!"
        assert event.data["tokens"] == {"total": 10}

    def test_tool_call_event(self) -> None:
        """tool_call() should create TOOL_CALL event."""
        event = tool_call("calculator", {"expression": "2+2"})

        assert event.event_type == EventType.TOOL_CALL
        assert event.data["tool_name"] == "calculator"
        assert event.data["payload"] == {"expression": "2+2"}

    def test_tool_result_event(self) -> None:
        """tool_result() should create TOOL_RESULT event."""
        event = tool_result("calculator", result=4, success=True)

        assert event.event_type == EventType.TOOL_RESULT
        assert event.data["tool_name"] == "calculator"
        assert event.data["result"] == 4
        assert event.data["success"] is True


class TestTraceSchema:
    """Tests for the TraceSchema class."""

    def test_schema_has_version(self) -> None:
        """Schema should have a version."""
        schema = TraceSchema()
        assert schema.version is not None
        assert "." in schema.version  # Should be semver-like

    def test_schema_compatibility_same_major(self) -> None:
        """Same major version should be compatible."""
        schema = TraceSchema(version="1.2.3")
        assert schema.is_compatible("1.0.0")
        assert schema.is_compatible("1.9.9")

    def test_schema_compatibility_different_major(self) -> None:
        """Different major version should be incompatible."""
        schema = TraceSchema(version="1.0.0")
        assert not schema.is_compatible("2.0.0")
        assert not schema.is_compatible("0.9.0")

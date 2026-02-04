"""
Tracing and session management for ThoughtFlow.

Traces capture complete run state: inputs, outputs, tool calls, model calls,
timing, token usage, and costs. This enables debugging, evaluation,
reproducibility, regression testing, and replay/diff across versions.

Example:
    >>> from thoughtflow.trace import Session
    >>>
    >>> session = Session()
    >>> response = agent.call(messages, session=session)
    >>>
    >>> # Inspect the trace
    >>> print(session.events)
    >>> print(session.total_tokens)
    >>> print(session.total_cost)
    >>>
    >>> # Save for replay
    >>> session.save("trace.json")
"""

from __future__ import annotations

from thoughtflow.trace.session import Session
from thoughtflow.trace.events import Event, EventType
from thoughtflow.trace.schema import TraceSchema

__all__ = [
    "Session",
    "Event",
    "EventType",
    "TraceSchema",
]

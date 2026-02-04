"""
Session object for ThoughtFlow.

A Session captures the complete state of an agent run, enabling
debugging, evaluation, reproducibility, and replay.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thoughtflow.trace.events import Event


@dataclass
class Session:
    """A session capturing the complete trace of an agent run.

    Sessions are the foundation for:
    - Debugging: See exactly what happened
    - Evaluation: Measure quality and performance
    - Reproducibility: Replay runs with same inputs
    - Regression testing: Diff across versions/models

    Attributes:
        session_id: Unique identifier for this session.
        created_at: When the session was created.
        events: List of events that occurred during the run.
        metadata: Additional session metadata.

    Example:
        >>> session = Session()
        >>> session.add_event(Event(type="call_start", data={...}))
        >>> session.add_event(Event(type="call_end", data={...}))
        >>>
        >>> # Get summary
        >>> print(session.summary())
        >>>
        >>> # Save for later
        >>> session.save("trace.json")
        >>>
        >>> # Load and replay
        >>> loaded = Session.load("trace.json")
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    events: list[Event] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Aggregated metrics (updated as events are added)
    _total_tokens: int = field(default=0, repr=False)
    _total_cost: float = field(default=0.0, repr=False)
    _total_duration_ms: int = field(default=0, repr=False)

    def add_event(self, event: Event) -> None:
        """Add an event to the session.

        Args:
            event: The event to add.
        """
        self.events.append(event)
        # TODO: Update aggregated metrics based on event type

    @property
    def total_tokens(self) -> int:
        """Total tokens used across all model calls."""
        return self._total_tokens

    @property
    def total_cost(self) -> float:
        """Total cost in USD across all model calls."""
        return self._total_cost

    @property
    def duration_ms(self) -> int:
        """Total duration in milliseconds."""
        return self._total_duration_ms

    def summary(self) -> dict[str, Any]:
        """Get a summary of the session.

        Returns:
            Dict with key metrics and counts.
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "event_count": len(self.events),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "duration_ms": self.duration_ms,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dict.

        Returns:
            Complete session data as a dict.
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
            "summary": self.summary(),
        }

    def save(self, path: str | Path) -> None:
        """Save the session to a JSON file.

        Args:
            path: Path to save to.
        """
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> Session:
        """Load a session from a JSON file.

        Args:
            path: Path to load from.

        Returns:
            Loaded Session instance.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement session loading with event deserialization
        raise NotImplementedError(
            "Session.load() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )

"""
Trace schema versioning for ThoughtFlow.

Once trace schemas are in use, downstream systems depend on them.
This module provides schema versioning to maintain backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Current schema version
SCHEMA_VERSION = "1.0.0"


@dataclass
class TraceSchema:
    """Schema metadata for trace files.

    Enables forward/backward compatibility as the trace format evolves.

    Attributes:
        version: Schema version string.
        thoughtflow_version: ThoughtFlow version that created the trace.
        features: List of optional features used in this trace.
    """

    version: str = SCHEMA_VERSION
    thoughtflow_version: str | None = None
    features: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict for embedding in trace files.

        Returns:
            Dict with schema information.
        """
        return {
            "schema_version": self.version,
            "thoughtflow_version": self.thoughtflow_version,
            "features": self.features or [],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceSchema:
        """Create from a dict.

        Args:
            data: Dict with schema information.

        Returns:
            TraceSchema instance.
        """
        return cls(
            version=data.get("schema_version", "1.0.0"),
            thoughtflow_version=data.get("thoughtflow_version"),
            features=data.get("features"),
        )

    def is_compatible(self, other_version: str) -> bool:
        """Check if this schema is compatible with another version.

        Compatibility rules:
        - Same major version = compatible
        - Different major version = incompatible

        Args:
            other_version: Version string to check against.

        Returns:
            True if compatible, False otherwise.
        """
        this_major = self.version.split(".")[0]
        other_major = other_version.split(".")[0]
        return this_major == other_major


def validate_trace(trace_data: dict[str, Any]) -> list[str]:
    """Validate a trace against the current schema.

    Args:
        trace_data: The trace data to validate.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check required fields
    if "session_id" not in trace_data:
        errors.append("Missing required field: session_id")

    if "events" not in trace_data:
        errors.append("Missing required field: events")
    elif not isinstance(trace_data["events"], list):
        errors.append("Field 'events' must be a list")

    # Check schema version compatibility
    schema_info = trace_data.get("schema", {})
    if schema_info:
        trace_version = schema_info.get("schema_version", "1.0.0")
        current_schema = TraceSchema()
        if not current_schema.is_compatible(trace_version):
            errors.append(
                f"Schema version mismatch: trace is v{trace_version}, "
                f"current is v{SCHEMA_VERSION}"
            )

    return errors

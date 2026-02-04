"""
Memory hooks for ThoughtFlow.

Memory integration is handled as a service boundary, not a magical built-in.
Memory is optional, pluggable, explicit at call-time, and recordable in traces.

Example:
    >>> from thoughtflow.memory import MemoryHook
    >>>
    >>> class VectorMemory(MemoryHook):
    ...     def retrieve(self, query, k=5):
    ...         # Retrieve relevant memories
    ...         return memories
    ...
    ...     def store(self, content, metadata=None):
    ...         # Store new memory
    ...         pass
"""

from __future__ import annotations

from thoughtflow.memory.base import MemoryHook, MemoryEvent

__all__ = [
    "MemoryHook",
    "MemoryEvent",
]

"""
Base memory interface for ThoughtFlow.

Memory hooks provide a clean pattern for memory integration:
- Memory retrieval produces context items
- Those items are explicitly inserted into the message list
- Memory writes are explicit events emitted by the agent run

This avoids:
- Hidden memory mutation
- "Where did this context come from?"
- Irreproducible behavior across runs
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryEvent:
    """An event representing a memory operation.

    Captured in traces to maintain full visibility into memory interactions.

    Attributes:
        event_type: Type of event (retrieve, store, delete).
        timestamp: When the event occurred.
        query: The retrieval query (for retrieve events).
        content: The content being stored (for store events).
        results: Retrieved memories (for retrieve events).
        metadata: Additional event metadata.
    """

    event_type: str  # "retrieve", "store", "delete"
    timestamp: datetime = field(default_factory=datetime.now)
    query: str | None = None
    content: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dict.

        Returns:
            Dict representation of the event.
        """
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "content": self.content,
            "results": self.results,
            "metadata": self.metadata,
        }


class MemoryHook(ABC):
    """Abstract base class for memory integrations.

    Memory hooks allow agents to:
    - Retrieve relevant context from long-term memory
    - Store new information for future retrieval
    - Maintain conversation history beyond context window

    Implementations might include:
    - Vector database (Pinecone, Weaviate, ChromaDB)
    - Key-value store
    - SQL database
    - File-based storage

    Example:
        >>> class SimpleMemory(MemoryHook):
        ...     def __init__(self):
        ...         self.memories = []
        ...
        ...     def retrieve(self, query, k=5):
        ...         # Simple keyword matching (real impl would use embeddings)
        ...         matches = [m for m in self.memories if query.lower() in m["content"].lower()]
        ...         return matches[:k]
        ...
        ...     def store(self, content, metadata=None):
        ...         self.memories.append({"content": content, "metadata": metadata or {}})
    """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant memories for a query.

        Args:
            query: The search query.
            k: Maximum number of results to return.
            filters: Optional filters to apply.

        Returns:
            List of memory dicts, each containing at least "content".
        """
        raise NotImplementedError

    @abstractmethod
    def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a new memory.

        Args:
            content: The content to store.
            metadata: Optional metadata to associate with the memory.

        Returns:
            ID of the stored memory.
        """
        raise NotImplementedError

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError("delete() not implemented for this memory hook")

    def clear(self) -> int:
        """Clear all memories.

        Returns:
            Number of memories deleted.
        """
        raise NotImplementedError("clear() not implemented for this memory hook")

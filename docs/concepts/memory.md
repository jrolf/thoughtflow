# Memory

Memory integration in ThoughtFlow is handled as a service boundary, not a magical built-in. Memory is optional, pluggable, explicit, and recordable.

---

## The Memory Hook Interface

```python
from thoughtflow.memory import MemoryHook

class MyMemory(MemoryHook):
    def retrieve(self, query, k=5, filters=None):
        """Retrieve relevant memories."""
        ...

    def store(self, content, metadata=None):
        """Store a new memory."""
        ...
```

---

## Basic Implementation

```python
from thoughtflow.memory import MemoryHook

class SimpleMemory(MemoryHook):
    def __init__(self):
        self.memories = []

    def retrieve(self, query, k=5, filters=None):
        # Simple keyword matching
        matches = []
        for m in self.memories:
            if query.lower() in m["content"].lower():
                matches.append(m)
        return matches[:k]

    def store(self, content, metadata=None):
        memory_id = str(len(self.memories))
        self.memories.append({
            "id": memory_id,
            "content": content,
            "metadata": metadata or {}
        })
        return memory_id
```

---

## Usage Pattern

Memory is explicitly used at call sites:

```python
# Retrieve relevant context
memories = memory.retrieve("user preferences")

# Build messages with memory context
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "system", "content": f"Relevant context: {memories}"},
    {"role": "user", "content": user_input},
]

# Call agent
response = agent.call(messages)

# Optionally store the interaction
memory.store(
    f"User: {user_input}\nAssistant: {response}",
    metadata={"type": "conversation"}
)
```

---

## Memory Events

Memory operations are tracked as events:

```python
from thoughtflow.memory import MemoryEvent

# Retrieve event
event = MemoryEvent(
    event_type="retrieve",
    query="user preferences",
    results=[...],
)

# Store event
event = MemoryEvent(
    event_type="store",
    content="New information...",
)
```

---

## Vector Database Example

```python
class VectorMemory(MemoryHook):
    def __init__(self, client, collection):
        self.client = client
        self.collection = collection

    def retrieve(self, query, k=5, filters=None):
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=filters,
        )
        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]

    def store(self, content, metadata=None):
        import uuid
        memory_id = str(uuid.uuid4())
        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[metadata or {}],
        )
        return memory_id
```

---

## Design Philosophy

- **Hooks, not hard-coding**: Memory is a service boundary
- **Explicit insertion**: Memory context explicitly added to messages
- **Traceable**: All memory operations recorded in session
- **Pluggable**: Swap implementations without changing agent code

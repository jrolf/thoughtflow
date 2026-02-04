#!/usr/bin/env python3
"""
ThoughtFlow Example 03: Memory Hooks

Demonstrates how to integrate memory with ThoughtFlow agents.
Memory is explicit - you control when to retrieve and store.

Prerequisites:
    pip install thoughtflow[openai]
    export OPENAI_API_KEY=sk-...

Run:
    python examples/03_memory_hooks.py
"""

from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter
from thoughtflow.memory import MemoryHook


class SimpleMemory(MemoryHook):
    """A simple in-memory implementation for demonstration."""

    def __init__(self):
        self.memories = []

    def retrieve(self, query, k=5, filters=None):
        """Simple keyword matching (real impl would use embeddings)."""
        matches = []
        query_lower = query.lower()

        for memory in self.memories:
            content_lower = memory["content"].lower()
            if query_lower in content_lower or any(
                word in content_lower for word in query_lower.split()
            ):
                matches.append(memory)

        return matches[:k]

    def store(self, content, metadata=None):
        """Store a new memory."""
        memory_id = f"mem_{len(self.memories)}"
        self.memories.append(
            {"id": memory_id, "content": content, "metadata": metadata or {}}
        )
        print(f"  [Memory] Stored: {content[:50]}...")
        return memory_id


def main():
    # Create memory instance
    memory = SimpleMemory()

    # Store some initial memories
    print("--- Storing Initial Memories ---")
    memory.store(
        "User's name is Alice and she works as a software engineer.",
        metadata={"type": "user_info"},
    )
    memory.store(
        "Alice prefers Python over JavaScript for backend development.",
        metadata={"type": "preference"},
    )
    memory.store(
        "Last conversation was about machine learning frameworks.",
        metadata={"type": "history"},
    )

    # Simulate a conversation with memory retrieval
    print("\n--- Simulating Conversation with Memory ---")

    user_input = "What programming language should I use?"

    # Step 1: Retrieve relevant memories
    print(f"\nUser: {user_input}")
    print("\n[Retrieving relevant memories...]")

    relevant_memories = memory.retrieve(user_input, k=3)
    for mem in relevant_memories:
        print(f"  - {mem['content']}")

    # Step 2: Build context-aware message list
    context = "\n".join([m["content"] for m in relevant_memories])

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "system",
            "content": f"Relevant context from memory:\n{context}",
        },
        {"role": "user", "content": user_input},
    ]

    print("\n[Message list with memory context:]")
    for msg in messages:
        role = msg["role"]
        content = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
        print(f"  {role}: {content}")

    # Step 3: Would call agent here
    # response = agent.call(messages)

    # Step 4: Store the interaction
    print("\n[Storing interaction in memory...]")
    memory.store(
        f"User asked about programming languages. Recommendation was based on their Python preference.",
        metadata={"type": "interaction"},
    )

    print("\n--- Memory State ---")
    print(f"Total memories: {len(memory.memories)}")


if __name__ == "__main__":
    main()

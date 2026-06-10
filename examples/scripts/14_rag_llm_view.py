"""
RAG with optional merged LLM view (issue #15).

Default ThoughtFlow behavior stores retrieved context as separate tagged events.
This example shows the opt-in path that folds augment events into the user
message for the LLM payload only — the event log stays unchanged.
"""

from thoughtflow import AGENT, LLM, MEMORY

DOCUMENTS = [
    "ThoughtFlow's MEMORY is an event-sourced state container.",
    "The universal contract is memory = primitive(memory).",
]


def retrieve(query):
    """Toy retriever — replace with your vector store or search API."""
    return [
        doc for doc in DOCUMENTS
        if any(word in doc.lower() for word in query.lower().split())
    ]


def inject_rag(memory, merge_into_user=False):
    question = memory.last_user_msg(content_only=True)
    context = "\n\n".join(retrieve(question))
    memory.add_augment(
        "Relevant context:\n" + context,
        metadata={"internal": True, "source": "rag"},
    )
    llm = LLM("openai:gpt-4o", key="sk-...")  # replace with your key
    agent = AGENT(llm=llm, merge_augments=merge_into_user)
    return agent(memory)


if __name__ == "__main__":
    memory = MEMORY()
    memory.add_msg("user", "What is the ThoughtFlow contract?")
    memory.add_augment(
        "Relevant context:\n" + DOCUMENTS[1],
        metadata={"internal": True, "source": "rag"},
    )

    print("Stored events (always separate):")
    for msg in memory.get_msgs():
        print(" ", msg["role"] + ":", msg["content"][:60])

    print("\nDefault LLM view (separate system message):")
    for msg in memory.get_llm_msgs():
        print(" ", msg["role"] + ":", msg["content"][:60])

    print("\nMerged LLM view (opt-in):")
    for msg in memory.get_llm_msgs(merge_augments=True):
        print(" ", msg["role"] + ":", msg["content"][:80])

# RAG, the ThoughtFlow Way

Retrieval-augmented generation in ThoughtFlow follows one doctrine: **retrieved context enters MEMORY as tagged events — never by mutating the user's original message.**

```python
memory.add_msg(
    "system",
    rag_context,
    metadata={"internal": True, "source": "rag"},
)
```

The user's message stays exactly as the user wrote it. The system's contribution is a separate, labeled event. (This doctrine was motivated by [issue #15](https://github.com/jrolf/thoughtflow/issues/15).)

---

## Why Not Stuff Context into the User Message?

The common RAG shortcut — rewriting the user's message to prepend retrieved chunks — destroys information. After the rewrite, the event log can no longer answer the most basic audit question: *what did the user actually say, and what did the system add?*

Because MEMORY is event-sourced, keeping the two apart is free and the payoff is real:

- **Auditability.** The log is a truthful record. Every injected chunk is an explicit event with a `source` tag, separable from genuine user input.
- **Debuggability.** When an answer is wrong, you can see precisely which context the model was given, on which turn.
- **Reusability.** The same conversation can be re-run with different retrieval (or none) because the user's messages were never contaminated.

---

## Filtering for the UI

Tagged events make display filtering one call. A chat UI should show the conversation, not the plumbing:

```python
# Everything the model sees
all_msgs = memory.get_msgs()

# What the user should see — internal events excluded
visible = memory.get_msgs(exclude_metadata={"internal": True})

# Just the injected context, for an audit view
injected = memory.get_msgs(metadata_filter={"source": "rag"})
```

The same memory serves the model (full context), the user (clean conversation), and the auditor (exactly what was added) — no parallel bookkeeping.

---

## A Complete Retrieval Flow

RAG in ThoughtFlow is ordinary Python composing two primitives: EMBED for vectors, THOUGHT for generation. Cosine similarity is five lines of stdlib:

```python
import math
from thoughtflow import EMBED, LLM, MEMORY, THOUGHT

embed = EMBED("openai:text-embedding-3-small", key="sk-...")
llm = LLM("openai:gpt-4o", key="sk-...")

documents = [
    "ThoughtFlow's MEMORY is an event-sourced state container.",
    "The universal contract is memory = primitive(memory).",
    "LLM reaches every provider through the standard library.",
]
doc_vectors = embed.call(documents)


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b)


def retrieve(query, k=2):
    qv = embed.call(query)
    scored = sorted(
        zip(documents, doc_vectors),
        key=lambda pair: cosine(qv, pair[1]),
        reverse=True,
    )
    return [doc for doc, _ in scored[:k]]


answer = THOUGHT(
    name="answer",
    llm=llm,
    prompt="Answer the question using the conversation context: {last_user_msg}",
)


def rag_flow(memory):
    question = memory.last_user_msg(content_only=True)
    context = "\n\n".join(retrieve(question))
    memory.add_msg(
        "system",
        "Relevant context:\n" + context,
        metadata={"internal": True, "source": "rag"},
    )
    return answer(memory)


memory = MEMORY()
memory.add_msg("user", "What is the ThoughtFlow contract?")
memory = rag_flow(memory)

print(memory.get_var("answer_result"))
print(memory.get_msgs(exclude_metadata={"internal": True}, repr="str"))
```

THOUGHT forwards the memory's messages to the LLM, so the tagged system event reaches the model like any other message — it is only the *record* that distinguishes it.

---

## Optional: Merged LLM View (Prompt Injection)

The default behavior above is intentional and unchanged. If you prefer the
popular pattern of injecting retrieved context *into the user message* for the
model — without mutating the stored event log — opt in at read time:

```python
from thoughtflow import AGENT, LLM, MEMORY

llm = LLM("openai:gpt-4o", key="sk-...")
memory = MEMORY()
memory.add_msg("user", "What is the ThoughtFlow contract?")
memory.add_augment(
    "Relevant context:\n" + context,
    metadata={"internal": True, "source": "rag"},
)

# Default: separate system message in the LLM payload (unchanged)
agent = AGENT(llm=llm)

# Opt-in: fold augment events into the user message for the LLM only
agent = AGENT(llm=llm, merge_augments=True)
```

`MEMORY.add_augment()` is sugar for `add_msg(..., metadata={"augments": "last_user", ...})`.
`MEMORY.get_llm_msgs(merge_augments=True)` builds the merged view without an agent.
Stored events, `get_msgs()`, UI filtering, and replay all behave exactly as before.

---

## Vector Stores Are Out of Scope

ThoughtFlow deliberately ships no vector store, no index, no retriever abstraction. Retrieval is a function that returns strings; where those strings come from is your choice — an in-memory list as above, SQLite, FAISS, pgvector, an HTTP search API. Compose with anything. The doctrine only governs the last step: how retrieved context enters MEMORY.

---

## Design Philosophy

- **The log tells the truth**: user words and system additions are separate events
- **Tags, not rewrites**: metadata marks provenance; storage is never mutated
- **Presentation is optional**: merge into the user LLM message only when you ask for it
- **One filter for every audience**: model, UI, and audit views from one memory
- **Retrieval is your code**: EMBED gives you vectors; the rest is plain Python

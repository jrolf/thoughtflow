# Deterministic Replay

LLM calls are the one nondeterministic, slow, costly piece of an AI system. ThoughtFlow makes them deterministic with record/replay: capture a live session once, then re-run the flow offline with byte-identical responses.

---

## The Design Insight

An event-sourced MEMORY is already a complete trace. Every message, variable change, and log entry is an ordered event. So instead of bolting on a separate session or trace object, ThoughtFlow records the LLM exchange itself as MEMORY events — request and response, keyed by a content hash.

The consequences fall out for free:

- **No new concepts.** Recording is `llm.record(memory)`. The recording is the memory.
- **No new serialization.** Recordings survive `memory.to_json()` / `MEMORY.from_json()` round trips like every other event.
- **No new replay machinery.** `LLM.replay(memory)` returns a `ReplayLLM` that is call-compatible with `LLM`, so it drops into any THOUGHT, AGENT, or WORKFLOW.

Replay matching is by content hash of the logical request (normalized messages, params minus transport-only keys, output schema). Same request in, same response out — regardless of which endpoint or key produced the recording.

---

## The Lifecycle: Record, Save, Replay, Assert

A complete runnable example:

```python
from thoughtflow import LLM, MEMORY, THOUGHT


def answer_flow(memory, llm):
    """Any memory -> memory callable works. Here: a single THOUGHT."""
    respond = THOUGHT(
        name="respond",
        llm=llm,
        prompt="Answer concisely: {last_user_msg}",
    )
    return respond(memory)


# 1. Record a live session
live = LLM("openai:gpt-4o", key="sk-...")
memory = MEMORY()
memory.add_msg("user", "What is the capital of France?")
live.record(memory)                     # every exchange now lands in memory
memory = answer_flow(memory, live)
original = memory.get_var("respond_result")

# 2. Save it — recordings are ordinary MEMORY events
memory.to_json("session.json")

# 3. Replay — no network, no API key
recorded = MEMORY.from_json("session.json")
replay_llm = LLM.replay(recorded)

fresh = MEMORY()
fresh.add_msg("user", "What is the capital of France?")
fresh = answer_flow(fresh, replay_llm)

# 4. Assert
assert fresh.get_var("respond_result") == original
```

The replayed flow runs in a fresh MEMORY against the recorded responses. If the flow is unchanged, the output is identical. If repeated identical requests were recorded, they replay in their recorded order.

`EMBED` mirrors this exactly: `embed.record(memory)` and `EMBED.replay(memory)` return a `ReplayEMBED` that serves recorded vectors.

---

## When the Flow Drifts: Miss Behavior

If a replayed flow issues a request that was never recorded — a prompt changed, a step was added — the `ReplayLLM` raises `ReplayMissError` by default. Failing loudly is the point: the recording no longer covers the flow.

```python
from thoughtflow import ReplayMissError

try:
    replay_llm.call([{"role": "user", "content": "An unrecorded request"}])
except ReplayMissError:
    print("Flow has drifted from the recording. Re-record.")
```

Note that primitives with their own error handling absorb the miss into their normal failure path: a THOUGHT, for example, retries and then stores `None` as its result with the error logged in memory, rather than letting the exception propagate. Either way, a drifted flow cannot silently produce stale answers.

For gradual re-recording, pass a live LLM as the fallback. Recorded requests replay; unrecorded ones go to the network:

```python
live = LLM("openai:gpt-4o", key="sk-...")
replay_llm = LLM.replay(recorded, on_miss=live)
```

If the memory contains recordings from more than one model, pass `model_id="service:model"` to choose which one to replay as.

---

## Replay in the Eval Harness

Replay turns evaluation into ordinary, fast, offline tests. The eval `Harness` runs any `memory -> memory` callable against a list of cases:

```python
from thoughtflow import LLM, MEMORY
from thoughtflow.eval import Harness, TestCase

replay_llm = LLM.replay(MEMORY.from_json("session.json"))

harness = Harness([
    TestCase(
        name="capital_of_france",
        setup=lambda m: m.add_msg("user", "What is the capital of France?"),
        check=lambda m: "Paris" in (m.last_asst_msg(content_only=True) or ""),
    ),
])

results = harness.run(lambda m: answer_flow(m, replay_llm))
print(results.summary())
assert results.pass_rate == 1.0, results.failures
```

Each case runs in a fresh, isolated MEMORY. Exceptions — including `ReplayMissError` — are contained as failures rather than aborting the run, so one drifted case does not hide the others.

`TestCase` also accepts `messages=[...]` instead of `setup`, and `expected=` (an exact string or a predicate over the final assistant message) instead of `check`.

---

## Design Philosophy

- **The memory is the trace**: no parallel session object to keep in sync
- **Fail loudly on drift**: a miss is a signal, not something to paper over
- **Drop-in**: a ReplayLLM goes anywhere an LLM goes
- **Tests are just Python**: record once, assert forever

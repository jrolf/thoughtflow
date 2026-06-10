#!/usr/bin/env python3
"""
ThoughtFlow Example 13: Record & Replay

Demonstrates deterministic testing of AI workflows — ThoughtFlow's
record/replay system, grown directly from the event-sourced MEMORY:

    1. RECORD:  llm.record(memory) captures every LLM exchange as events
    2. PERSIST: memory.to_json('session.json') — the memory IS the recording
    3. REPLAY:  LLM.replay(memory) serves recorded responses offline
    4. EVAL:    the eval Harness runs a flow against test cases

Replay runs are byte-identical, instant, free, and need no API keys —
perfect for CI, regression tests, and debugging production sessions.

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (only needed for the initial recording;
                                   a mock LLM is used when no key is set)

Run:
    python examples/scripts/13_record_replay.py
"""

import os
from thoughtflow import LLM, MEMORY, THOUGHT, ReplayMissError
from thoughtflow.eval import Harness, TestCase


# =============================================================================
# A flow: any memory -> memory callable built from primitives
# =============================================================================

def build_flow(llm):
    """A simple flow that answers the user's question."""
    thought = THOUGHT(
        name="answer",
        llm=llm,
        prompt="Answer concisely: {last_user_msg}",
    )

    def flow(memory):
        return thought(memory)

    return flow


class MockLLM(LLM):
    """Offline stand-in so the example runs without an API key."""

    def __init__(self):
        super().__init__("openai:gpt-4o-mini", key="mock")

    def call(self, msg_list, params={}, output_schema=None, stream=False):
        merged = {**self.default_params, **params}
        recording = self._record_memory is not None
        if recording:
            key, request = self._request_signature(msg_list, merged, output_schema)
        choices = ["The capital of France is Paris."]
        if recording:
            self._record_exchange(key, request, choices)
        return choices


# =============================================================================
# Step 1+2: Record a session and persist it
# =============================================================================

def record_session(path):
    """Run the flow once against a live (or mock) LLM, recording exchanges."""
    print("=" * 60)
    print("Step 1: RECORD — run the flow live, capture every exchange")
    print("=" * 60)

    if os.getenv("OPENAI_API_KEY"):
        llm = LLM("openai:gpt-4o-mini", key=os.environ["OPENAI_API_KEY"])
    else:
        print("(no OPENAI_API_KEY — using a mock LLM for the recording)")
        llm = MockLLM()

    recording = MEMORY()
    llm.record(recording)            # every call is now captured

    memory = MEMORY()
    memory.add_msg("user", "What is the capital of France?")
    memory = build_flow(llm)(memory)

    answer = memory.get_var("answer_result")
    print("Live answer: {}".format(answer))
    print("Exchanges recorded: {}".format(len(recording.get_exchanges())))

    recording.to_json(path)          # the memory IS the recording
    print("Recording saved to {}".format(path))
    return answer


# =============================================================================
# Step 3: Replay the session deterministically — no network, no keys
# =============================================================================

def replay_session(path, live_answer):
    """Re-run the same flow against the recording. Offline. Identical."""
    print()
    print("=" * 60)
    print("Step 2: REPLAY — same flow, no network, identical output")
    print("=" * 60)

    recorded = MEMORY.from_json(path)
    replay_llm = LLM.replay(recorded)   # drop-in LLM, serves recordings

    memory = MEMORY()
    memory.add_msg("user", "What is the capital of France?")
    memory = build_flow(replay_llm)(memory)

    replayed = memory.get_var("answer_result")
    print("Replayed answer: {}".format(replayed))
    print("Matches live run: {}".format(replayed == live_answer))

    # Drift fails loudly: an unrecorded request raises ReplayMissError
    try:
        replay_llm.call([{"role": "user", "content": "never recorded"}])
    except ReplayMissError:
        print("Unrecorded request correctly raised ReplayMissError")

    return replay_llm


# =============================================================================
# Step 4: Eval harness — structured test cases over any flow
# =============================================================================

def run_eval(replay_llm):
    """Run the flow against test cases, fully offline via replay."""
    print()
    print("=" * 60)
    print("Step 3: EVAL — harness of test cases over the replayed flow")
    print("=" * 60)

    harness = Harness([
        TestCase(
            name="capital_of_france",
            setup=lambda m: m.add_msg("user", "What is the capital of France?"),
            check=lambda m: "paris" in (m.get_var("answer_result") or "").lower(),
        ),
    ])

    results = harness.run(build_flow(replay_llm))
    print("Results: {}".format(results.summary()))


# =============================================================================
# Main
# =============================================================================

def main():
    path = "/tmp/thoughtflow_session.json"
    live_answer = record_session(path)
    replay_llm = replay_session(path, live_answer)
    run_eval(replay_llm)
    print("\nDone. The recording at {} can be committed to your repo".format(path))
    print("and replayed in CI forever — no keys, no cost, no flakiness.")


if __name__ == "__main__":
    main()

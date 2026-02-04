#!/usr/bin/env python3
"""
ThoughtFlow Example 04: Trace and Replay

Demonstrates how to capture execution traces and use them for
debugging, evaluation, and replay testing.

Prerequisites:
    pip install thoughtflow

Run:
    python examples/04_trace_replay.py
"""

import json
from datetime import datetime

from thoughtflow.trace import Session, Event, EventType
from thoughtflow.trace.events import call_start, call_end, tool_call, tool_result


def main():
    # Create a session to capture the trace
    print("--- Creating Session ---")
    session = Session(metadata={"example": "trace_replay", "version": "1.0"})
    print(f"Session ID: {session.session_id}")
    print(f"Created at: {session.created_at}")

    # Simulate an agent run by adding events
    print("\n--- Simulating Agent Run ---")

    # 1. Call starts
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What is 25 * 4?"},
    ]
    event = call_start(messages, params={"model": "gpt-4", "temperature": 0})
    session.add_event(event)
    print("Event: call_start")

    # 2. Tool is called
    event = tool_call("calculator", {"expression": "25 * 4"})
    session.add_event(event)
    print("Event: tool_call (calculator)")

    # 3. Tool returns
    event = tool_result("calculator", result=100, success=True)
    session.add_event(event)
    print("Event: tool_result (100)")

    # 4. Call ends
    event = call_end("25 * 4 = 100", tokens={"prompt": 25, "completion": 10, "total": 35})
    session.add_event(event)
    print("Event: call_end")

    # Show session summary
    print("\n--- Session Summary ---")
    summary = session.summary()
    print(json.dumps(summary, indent=2))

    # Show all events
    print("\n--- All Events ---")
    for i, event in enumerate(session.events):
        event_type = (
            event.event_type.value
            if isinstance(event.event_type, EventType)
            else event.event_type
        )
        print(f"{i + 1}. {event_type}: {list(event.data.keys())}")

    # Convert to dict (for serialization)
    print("\n--- Serialized Session ---")
    session_dict = session.to_dict()
    print(f"Keys: {list(session_dict.keys())}")
    print(f"Event count: {len(session_dict['events'])}")

    # Save to file (demonstration)
    print("\n--- Save/Load (simulated) ---")
    print("Would save to: trace_example.json")
    print("Session data is JSON-serializable and can be saved/loaded for replay")

    # Show how traces enable testing
    print("\n--- Trace-Based Testing Pattern ---")
    print("""
    # Save a golden trace
    session.save("golden.json")

    # Later, replay and compare:
    from thoughtflow.eval import Replay

    replay = Replay.load("golden.json")
    result = replay.run(agent)

    assert result.success
    assert result.replayed_response == result.original_response
    """)


if __name__ == "__main__":
    main()

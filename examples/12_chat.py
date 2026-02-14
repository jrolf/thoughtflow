#!/usr/bin/env python3
"""
ThoughtFlow Example 12: Interactive Chat

Demonstrates how to use the CHAT class to test agent behavior
interactively in a terminal or Jupyter notebook.

Two patterns are shown:
    1. chat.run()  — launches an interactive loop (type 'q' to exit)
    2. chat.turn() — programmatic single-turn calls (great for notebooks)

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (optional, uses a mock agent by default)

Run:
    python examples/12_chat.py
"""

import os
from thoughtflow import MEMORY, THOUGHT, CHAT, LLM


# =============================================================================
# Mock agent (works without an API key)
# =============================================================================

def mock_agent(memory):
    """
    A simple mock agent that echoes the user's message.

    Any callable with signature fn(memory) -> memory works with CHAT.
    """
    user_msg = memory.last_user_msg(content_only=True) or ""
    reply = "I heard you say: '{}'".format(user_msg)
    memory.add_msg("assistant", reply, channel="chat")
    return memory


# =============================================================================
# Pattern 1: Interactive loop with chat.run()
# =============================================================================

def demo_interactive():
    """Launch an interactive chat session.  Type 'q' or 'quit' to exit."""
    print("=" * 50)
    print("Pattern 1: Interactive loop — chat.run()")
    print("=" * 50)

    # Use a real LLM if an API key is available, otherwise fall back to mock.
    if os.getenv("OPENAI_API_KEY"):
        llm = LLM("openai:gpt-4o-mini", key=os.environ["OPENAI_API_KEY"])
        agent = THOUGHT(
            name="respond",
            llm=llm,
            prompt="You are a helpful assistant. Respond to: {last_user_msg}",
        )
    else:
        agent = mock_agent

    chat = CHAT(
        agent,
        greeting="Hello! I'm your assistant. Type 'q' to quit.",
    )
    chat.run()

    # After the session you can inspect what happened:
    print("\n--- Session history ({} turns) ---".format(len(chat.history)))
    for i, (user_text, agent_text) in enumerate(chat.history, 1):
        print("  Turn {}: user='{}' -> agent='{}'".format(i, user_text, agent_text))


# =============================================================================
# Pattern 2: Programmatic / cell-by-cell with chat.turn()
# =============================================================================

def demo_programmatic():
    """Use turn() for programmatic or Jupyter cell-by-cell interaction."""
    print("\n" + "=" * 50)
    print("Pattern 2: Programmatic — chat.turn()")
    print("=" * 50)

    chat = CHAT(mock_agent)

    # Each call to turn() is one user→agent exchange.
    response1 = chat.turn("What is ThoughtFlow?")
    print("Response 1:", response1)

    response2 = chat.turn("Tell me more.")
    print("Response 2:", response2)

    # Inspect accumulated history
    print("\nHistory:", chat.history)

    # The underlying memory is always accessible
    print("\nMessages in memory:", len(chat.memory.get_msgs()))


# =============================================================================

if __name__ == "__main__":
    # Run the programmatic demo first (no user input needed)
    demo_programmatic()

    # Then launch the interactive demo
    demo_interactive()

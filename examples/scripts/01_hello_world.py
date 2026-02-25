#!/usr/bin/env python3
"""
ThoughtFlow Example 01: Hello World

The simplest possible ThoughtFlow example - create an LLM and make a call.

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...

Run:
    python examples/01_hello_world.py
"""

import os
from thoughtflow import LLM, MEMORY, THOUGHT


def main():
    # 1. Create an LLM instance with your provider
    # Format: "service:model" (e.g., "openai:gpt-4o", "anthropic:claude-3-sonnet")
    api_key = os.environ.get("OPENAI_API_KEY", "your-api-key")
    llm = LLM("openai:gpt-4o", key=api_key)

    # 2. Create a MEMORY to store conversation state
    memory = MEMORY()

    # 3. Add a user message to memory
    memory.add_msg("user", "What is ThoughtFlow in one sentence?", channel="cli")

    # 4. Create a THOUGHT that responds to the user
    thought = THOUGHT(
        name="respond",
        llm=llm,
        prompt="You are a helpful assistant. Respond to the user's question: {last_user_msg}",
    )

    # 5. Execute the thought (this calls the LLM and stores the result)
    print("Calling LLM...")
    memory = thought(memory)

    # 6. Get the result
    result = memory.get_var("respond_result")
    print(f"\nResponse: {result}")

    # You can also see the full conversation
    print("\n--- Full Conversation ---")
    print(memory.render(output_format='conversation'))


if __name__ == "__main__":
    main()

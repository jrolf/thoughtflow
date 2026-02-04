#!/usr/bin/env python3
"""
ThoughtFlow Example 01: Hello World

The simplest possible ThoughtFlow example - create an agent and make a call.

Prerequisites:
    pip install thoughtflow[openai]
    export OPENAI_API_KEY=sk-...

Run:
    python examples/01_hello_world.py
"""

from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter


def main():
    # 1. Create an adapter for your provider
    # (Uses OPENAI_API_KEY environment variable by default)
    adapter = OpenAIAdapter()

    # 2. Create an agent
    agent = Agent(adapter)

    # 3. Prepare messages (the universal currency in ThoughtFlow)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is ThoughtFlow in one sentence?"},
    ]

    # 4. Call the agent
    print("Calling agent...")
    response = agent.call(messages)

    print(f"\nResponse: {response}")


if __name__ == "__main__":
    main()

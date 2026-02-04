#!/usr/bin/env python3
"""
ThoughtFlow Example 05: Multi-Provider

Demonstrates how to use ThoughtFlow with different providers
using the same interface.

Prerequisites:
    pip install thoughtflow[all-providers]
    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...

Run:
    python examples/05_multi_provider.py
"""

import os

from thoughtflow import Agent


def create_agents():
    """Create agents for different providers."""
    agents = {}

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        from thoughtflow.adapters import OpenAIAdapter

        agents["openai"] = Agent(OpenAIAdapter())
        print("✓ OpenAI adapter configured")
    else:
        print("✗ OpenAI: OPENAI_API_KEY not set")

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        from thoughtflow.adapters import AnthropicAdapter

        agents["anthropic"] = Agent(AnthropicAdapter())
        print("✓ Anthropic adapter configured")
    else:
        print("✗ Anthropic: ANTHROPIC_API_KEY not set")

    # Local (Ollama) - no API key needed
    try:
        from thoughtflow.adapters import LocalAdapter

        agents["local"] = Agent(LocalAdapter(base_url="http://localhost:11434/v1"))
        print("✓ Local adapter configured (Ollama)")
    except Exception as e:
        print(f"✗ Local: {e}")

    return agents


def main():
    print("--- ThoughtFlow Multi-Provider Demo ---\n")

    # Create agents
    print("Configuring providers:")
    agents = create_agents()

    if not agents:
        print("\nNo providers configured. Set API keys or start Ollama.")
        return

    # Same messages work with all providers
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": "What is 2 + 2? Reply with just the number."},
    ]

    print(f"\n--- Sending same message to {len(agents)} provider(s) ---")
    print(f"Message: {messages[-1]['content']}")

    # Call each agent with the same interface
    for name, agent in agents.items():
        print(f"\n[{name.upper()}]")
        try:
            # Same call() interface for all providers!
            response = agent.call(messages)
            print(f"Response: {response}")
        except NotImplementedError:
            print("(Not yet implemented - placeholder)")
        except Exception as e:
            print(f"Error: {e}")

    # Show the power of a unified interface
    print("\n--- Key Benefit ---")
    print("""
    The same code works with any provider:

        agent = Agent(adapter)  # Any adapter!
        response = agent.call(messages)

    Switch providers by changing one line:
        - OpenAIAdapter() → AnthropicAdapter()
        - Test locally with LocalAdapter()
        - No changes to your agent logic!
    """)


if __name__ == "__main__":
    main()

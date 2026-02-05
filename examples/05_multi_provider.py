#!/usr/bin/env python3
"""
ThoughtFlow Example 05: Multi-Provider LLM

Demonstrates how to use ThoughtFlow's LLM class with different providers
using the same unified interface.

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...
    export GROQ_API_KEY=gsk_...

Run:
    python examples/05_multi_provider.py
"""

import os

from thoughtflow import LLM, MEMORY, THOUGHT


def create_llms():
    """Create LLM instances for different providers."""
    llms = {}

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        llms["openai"] = LLM("openai:gpt-4o", key=os.environ["OPENAI_API_KEY"])
        print("✓ OpenAI configured (gpt-4o)")
    else:
        print("✗ OpenAI: OPENAI_API_KEY not set")

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        llms["anthropic"] = LLM("anthropic:claude-3-sonnet-20240229", key=os.environ["ANTHROPIC_API_KEY"])
        print("✓ Anthropic configured (claude-3-sonnet)")
    else:
        print("✗ Anthropic: ANTHROPIC_API_KEY not set")

    # Groq
    if os.getenv("GROQ_API_KEY"):
        llms["groq"] = LLM("groq:llama-3.1-8b-instant", key=os.environ["GROQ_API_KEY"])
        print("✓ Groq configured (llama-3.1-8b)")
    else:
        print("✗ Groq: GROQ_API_KEY not set")

    # Ollama (local) - no API key needed
    llms["ollama"] = LLM("ollama:llama3.2", key="")
    print("✓ Ollama configured (local, llama3.2)")

    return llms


def main():
    print("--- ThoughtFlow Multi-Provider Demo ---\n")

    # Create LLM instances
    print("Configuring providers:")
    llms = create_llms()

    if not llms:
        print("\nNo providers configured. Set API keys or start Ollama.")
        return

    # Same message works with all providers
    user_message = "What is 2 + 2? Reply with just the number."

    print(f"\n--- Sending same message to {len(llms)} provider(s) ---")
    print(f"Message: {user_message}")

    # Test each LLM with the same interface
    for name, llm in llms.items():
        print(f"\n[{name.upper()}]")
        
        try:
            # Create a fresh memory for each provider
            memory = MEMORY()
            memory.add_msg("user", user_message, channel="cli")

            # Create a THOUGHT with this LLM
            thought = THOUGHT(
                name="respond",
                llm=llm,
                prompt="Be concise. {last_user_msg}",
            )

            # Execute the thought
            memory = thought(memory)
            result = memory.get_var("respond_result")
            print(f"Response: {result}")
            
        except Exception as e:
            print(f"Error: {e}")

    # --- Direct LLM Call Example ---
    print("\n--- Direct LLM Call (Lower-level API) ---")
    
    if os.getenv("OPENAI_API_KEY"):
        llm = LLM("openai:gpt-4o", key=os.environ["OPENAI_API_KEY"])
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is the capital of France?"},
        ]
        
        # Direct call returns a list of choices
        responses = llm.call(messages)
        print(f"Direct call result: {responses[0]}")

    # Show the power of a unified interface
    print("\n--- Key Benefits ---")
    print("""
    The LLM class provides a unified interface:

        llm = LLM("provider:model", key="...")
        responses = llm.call(messages)

    Switch providers by changing one line:
        - LLM("openai:gpt-4o", ...)
        - LLM("anthropic:claude-3-sonnet", ...)
        - LLM("groq:llama-3.1-8b-instant", ...)
        - LLM("ollama:llama3.2", ...)
        - LLM("gemini:gemini-pro", ...)
        - LLM("openrouter:mistralai/mistral-7b", ...)

    No changes to your application logic!
    """)


if __name__ == "__main__":
    main()

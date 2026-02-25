#!/usr/bin/env python3
"""
ThoughtFlow Example 09: DECIDE — Constrained Decision Steps

Demonstrates the DECIDE class for constraining LLM output to finite choices:
- Simple list of choices
- Dict with descriptions for each choice
- Smart parsing (exact match, embedded, case-insensitive)
- Automatic retry with choice-specific repair prompts
- Default fallback when all retries fail

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (for LLM examples)

Run:
    python examples/09_decide.py
"""

import os
from thoughtflow import MEMORY, DECIDE, LLM


# Create a mock LLM for examples that don't need real API calls
class MockLLM:
    """A mock LLM that returns predefined responses for demonstration."""
    
    def __init__(self, responses=None):
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.last_msgs = None
    
    def call(self, msgs, params=None, **kwargs):
        """Mock LLM call that returns predefined responses."""
        self.last_msgs = msgs
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return [response]


def main():
    print("--- ThoughtFlow DECIDE Demo ---\n")
    
    # =========================================================================
    # Part 1: Simple List of Choices
    # =========================================================================
    print("=== Part 1: Simple List of Choices ===\n")
    
    mock_llm = MockLLM(responses=["positive"])
    memory = MEMORY()
    
    # DECIDE with a simple list of choices
    sentiment = DECIDE(
        name="classify_sentiment",
        llm=mock_llm,
        choices=["positive", "negative", "neutral"],
        prompt="Classify the sentiment of: {text}",
    )
    
    memory.set_var("text", "I absolutely love this product! Best purchase ever!")
    memory = sentiment(memory)
    
    result = memory.get_var("classify_sentiment_result")
    print(f"Text: 'I absolutely love this product! Best purchase ever!'")
    print(f"Sentiment: {result}")
    print(f"Choices were: {sentiment._choices_list}")

    # =========================================================================
    # Part 2: Dict with Descriptions
    # =========================================================================
    print("\n=== Part 2: Dict with Descriptions ===\n")
    
    mock_llm = MockLLM(responses=["escalate"])
    memory = MEMORY()
    
    # DECIDE with dict format (descriptions are shown to the LLM)
    router = DECIDE(
        name="route_ticket",
        llm=mock_llm,
        choices={
            "approve": "Accept the request and process immediately",
            "reject": "Deny the request with a polite explanation",
            "escalate": "Forward to a human supervisor for review",
        },
        prompt="Review this support ticket and decide how to handle it:\n\n{ticket}",
    )
    
    memory.set_var("ticket", "Customer claims they were charged twice but only received one item.")
    memory = router(memory)
    
    result = memory.get_var("route_ticket_result")
    print(f"Ticket: 'Customer claims they were charged twice...'")
    print(f"Decision: {result}")
    print(f"\nFormatted choices shown to LLM:")
    print(router._format_choices())

    # =========================================================================
    # Part 3: Smart Parsing
    # =========================================================================
    print("\n=== Part 3: Smart Parsing ===\n")
    
    # DECIDE handles various LLM response formats
    decide = DECIDE(
        name="test",
        llm=MockLLM(),
        choices=["approve", "reject", "escalate"],
        prompt="Test",
    )
    
    # Test various response formats
    test_cases = [
        ("approve", "Exact match"),
        ("APPROVE", "Case variation (uppercase)"),
        ("Approve", "Case variation (title case)"),
        ("I would choose approve for this case.", "Embedded in sentence"),
        ("My decision is: reject", "With prefix"),
        ("  escalate  ", "With whitespace"),
    ]
    
    for response, description in test_cases:
        parsed = decide.parse_response(response)
        valid, _ = decide.validate(parsed)
        print(f"  '{response}' → '{parsed}' (valid: {valid}) [{description}]")

    # =========================================================================
    # Part 4: Retry with Choice-Specific Repair
    # =========================================================================
    print("\n=== Part 4: Retry with Choice-Specific Repair ===\n")
    
    # LLM that gives invalid responses first, then valid
    mock_llm = MockLLM(responses=[
        "I think maybe we should consider all options carefully...",  # Invalid
        "The answer depends on many factors...",                       # Invalid
        "approve",                                                     # Valid!
    ])
    
    memory = MEMORY()
    
    decide = DECIDE(
        name="retry_demo",
        llm=mock_llm,
        choices=["approve", "reject"],
        prompt="Make a decision",
        max_retries=5,  # DECIDE defaults to 5 retries
    )
    
    memory = decide(memory)
    result = memory.get_var("retry_demo_result")
    
    print(f"LLM was called {mock_llm.call_count} times before success")
    print(f"Final result: {result}")
    print(f"\nRepair prompt used: {decide._build_repair_suffix('invalid')}")

    # =========================================================================
    # Part 5: Default Fallback
    # =========================================================================
    print("\n=== Part 5: Default Fallback ===\n")
    
    # LLM that never gives a valid response
    mock_llm = MockLLM(responses=["I cannot decide"] * 10)
    memory = MEMORY()
    
    decide = DECIDE(
        name="fallback_demo",
        llm=mock_llm,
        choices=["proceed", "abort"],
        prompt="Should we proceed?",
        default="abort",      # Use this if all retries fail
        max_retries=2,        # Only try twice
    )
    
    memory = decide(memory)
    result = memory.get_var("fallback_demo_result")
    
    print(f"LLM never gave valid response (tried {mock_llm.call_count} times)")
    print(f"Default was used: '{result}'")

    # =========================================================================
    # Part 6: DECIDE is a THOUGHT
    # =========================================================================
    print("\n=== Part 6: DECIDE Inherits from THOUGHT ===\n")
    
    from thoughtflow import THOUGHT
    
    # DECIDE has all THOUGHT features
    mock_llm = MockLLM(responses=["yes"])
    
    decide = DECIDE(
        name="inherited_features",
        llm=mock_llm,
        choices=["yes", "no"],
        prompt="Confirm: {question}",
    )
    
    print(f"DECIDE is subclass of THOUGHT: {issubclass(DECIDE, THOUGHT)}")
    print(f"Has execution_history: {hasattr(decide, 'execution_history')}")
    print(f"Has to_dict: {hasattr(decide, 'to_dict')}")
    print(f"Has copy: {hasattr(decide, 'copy')}")
    
    # Execute and check history
    memory = MEMORY()
    memory.set_var("question", "Do you want to continue?")
    memory = decide(memory)
    
    print(f"\nAfter execution:")
    print(f"  execution_history entries: {len(decide.execution_history)}")
    print(f"  last_result: {decide.last_result}")
    print(f"  last_error: {decide.last_error}")

    # =========================================================================
    # Part 7: Serialization
    # =========================================================================
    print("\n=== Part 7: Serialization ===\n")
    
    decide = DECIDE(
        name="serialize_demo",
        llm=MockLLM(),
        choices={"opt_a": "Option A", "opt_b": "Option B"},
        prompt="Choose an option",
        default="opt_a",
    )
    
    # Serialize to dict
    data = decide.to_dict()
    
    print("Serialized DECIDE:")
    print(f"  name: {data['name']}")
    print(f"  choices: {data['choices']}")
    print(f"  default: {data['default']}")
    print(f"  _class: {data['_class']}")
    
    # Reconstruct from dict
    restored = DECIDE.from_dict(data, llm=MockLLM())
    print(f"\nRestored: {restored}")

    # =========================================================================
    # Part 8: String Representations
    # =========================================================================
    print("\n=== Part 8: String Representations ===\n")
    
    decide = DECIDE(
        name="repr_demo",
        llm=MockLLM(),
        choices=["a", "b", "c"],
        prompt="Choose",
        default="a",
    )
    
    print(f"repr(): {repr(decide)}")
    print(f"str():  {str(decide)}")

    # =========================================================================
    # Part 9: Real-World Example — Intent Classification
    # =========================================================================
    print("\n=== Part 9: Real-World Example ===\n")
    
    # Simulate intent classification for a chatbot
    mock_llm = MockLLM(responses=["track_order"])
    memory = MEMORY()
    
    intent_classifier = DECIDE(
        name="classify_intent",
        llm=mock_llm,
        choices={
            "track_order": "User wants to track an existing order",
            "return_item": "User wants to return or exchange an item",
            "product_info": "User is asking about product details or availability",
            "billing": "User has a question about charges or payments",
            "other": "Query doesn't fit other categories",
        },
        prompt="""Classify the user's intent based on their message.

User message: {user_message}

Consider the context and choose the most appropriate intent.""",
        default="other",
    )
    
    memory.set_var("user_message", "Where is my package? I ordered it 3 days ago.")
    memory = intent_classifier(memory)
    
    intent = memory.get_var("classify_intent_result")
    print(f"User: 'Where is my package? I ordered it 3 days ago.'")
    print(f"Classified intent: {intent}")
    
    # You could then route to different handlers based on intent
    handlers = {
        "track_order": "→ Route to order tracking system",
        "return_item": "→ Route to returns portal",
        "product_info": "→ Route to product database",
        "billing": "→ Route to billing support",
        "other": "→ Route to general support",
    }
    print(f"Action: {handlers.get(intent, 'Unknown')}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n=== Summary ===")
    print("""
    DECIDE is a specialized THOUGHT for constrained decisions:
    
    1. Choices Format:
       - List: ["a", "b", "c"]
       - Dict: {"a": "Description of A", "b": "Description of B"}
    
    2. Smart Parsing:
       - Exact match: "approve" → "approve"
       - Case-insensitive: "APPROVE" → "approve" 
       - Embedded: "I choose approve" → "approve"
    
    3. Retry Behavior:
       - Defaults to max_retries=5 (vs THOUGHT's 1)
       - Choice-specific repair: "Respond with exactly one of: a, b, c"
    
    4. Fallback:
       - default="value" used when all retries fail
    
    5. Inherits from THOUGHT:
       - Full serialization (to_dict/from_dict)
       - Execution history tracking
       - Pre/post hooks
       - copy() method
    
    Use DECIDE for:
    - Intent classification
    - Routing decisions  
    - Yes/no confirmations
    - Category selection
    - Any constrained choice from a finite set
    """)


if __name__ == "__main__":
    main()

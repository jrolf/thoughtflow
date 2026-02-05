#!/usr/bin/env python3
"""
ThoughtFlow Example 05: Advanced THOUGHT Features

Demonstrates advanced THOUGHT capabilities beyond basic LLM calls:
- Different operations (memory_query, variable_set, conditional)
- Schema-based parsing with parsing_rules
- Built-in and custom validators
- Retry logic with automatic repair prompts
- Pre/post hooks for custom processing
- Required and optional variables

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (for LLM examples)

Run:
    python examples/05_thought_advanced.py
"""

import os
from thoughtflow import MEMORY, THOUGHT, LLM, valid_extract


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
    print("--- ThoughtFlow Advanced THOUGHT Demo ---\n")
    
    # =========================================================================
    # Part 1: Memory Query Operation (No LLM)
    # =========================================================================
    print("=== Part 1: Memory Query Operation ===\n")
    
    memory = MEMORY()
    memory.set_var("user_name", "Alice")
    memory.set_var("user_role", "admin")
    memory.set_var("session_id", "sess_12345")
    
    # Create a thought that queries memory without calling an LLM
    query_thought = THOUGHT(
        name="get_user_context",
        operation="memory_query",
        required_vars=["user_name", "session_id"],  # These MUST exist
        optional_vars=["user_role", "preferences"]   # These are nice-to-have
    )
    
    memory = query_thought(memory)
    result = memory.get_var("get_user_context_result")
    
    print(f"Memory query result: {result}")
    print(f"  Found user_name: {result.get('user_name')}")
    print(f"  Found session_id: {result.get('session_id')}")
    print(f"  Found optional user_role: {result.get('user_role')}")
    print(f"  Missing optional preferences: {result.get('preferences')}")

    # =========================================================================
    # Part 2: Variable Set Operation
    # =========================================================================
    print("\n=== Part 2: Variable Set Operation ===\n")
    
    memory = MEMORY()
    
    # Create a thought that sets multiple variables at once
    init_thought = THOUGHT(
        name="init_session",
        operation="variable_set",
        prompt={  # Dict of variables to set
            "session_active": True,
            "turn_count": 0,
            "mode": "assistant"
        }
    )
    
    memory = init_thought(memory)
    
    print("Variables set by thought:")
    print(f"  session_active: {memory.get_var('session_active')}")
    print(f"  turn_count: {memory.get_var('turn_count')}")
    print(f"  mode: {memory.get_var('mode')}")

    # =========================================================================
    # Part 3: Conditional Operation
    # =========================================================================
    print("\n=== Part 3: Conditional Operation ===\n")
    
    memory = MEMORY()
    memory.set_var("user_role", "admin")
    
    # Create a thought that executes different logic based on condition
    auth_thought = THOUGHT(
        name="check_auth",
        operation="conditional",
        condition=lambda mem, ctx: mem.get_var("user_role") == "admin",
        if_true={"authorized": True, "access_level": "full"},
        if_false={"authorized": False, "access_level": "limited"}
    )
    
    memory = auth_thought(memory)
    result = memory.get_var("check_auth_result")
    
    print(f"Authorization check: {result}")

    # =========================================================================
    # Part 4: Schema-Based Parsing with parsing_rules
    # =========================================================================
    print("\n=== Part 4: Schema-Based Parsing ===\n")
    
    # Mock LLM that returns structured data
    mock_llm = MockLLM(responses=[
        """
        Based on my analysis, here's the task breakdown:
        
        ```python
        {
            'task_name': 'Deploy to Production',
            'priority': 1,
            'steps': ['Build', 'Test', 'Deploy'],
            'estimated_hours': 4.5
        }
        ```
        """
    ])
    
    memory = MEMORY()
    memory.add_msg("user", "Break down the deployment task", channel="api")
    
    # THOUGHT with parsing_rules automatically uses valid_extract
    parse_thought = THOUGHT(
        name="parse_task",
        llm=mock_llm,
        prompt="Analyze the task and return structured data.",
        parsing_rules={
            "kind": "python",
            "format": {
                "task_name": "",
                "priority": 0,
                "steps": [],
                "estimated_hours": 0.0
            }
        },
        channel="api"  # Must specify valid channel for message logging
    )
    
    memory = parse_thought(memory)
    result = memory.get_var("parse_task_result")
    
    if result:
        print(f"Parsed task: {result['task_name']}")
        print(f"Priority: {result['priority']}")
        print(f"Steps: {result['steps']}")
        print(f"Hours: {result['estimated_hours']}")
    else:
        print(f"Parsing failed. Error: {parse_thought.last_error}")

    # =========================================================================
    # Part 5: Built-in Validators
    # =========================================================================
    print("\n=== Part 5: Built-in Validators ===\n")
    
    # Validator: has_keys (check required keys in dict)
    mock_llm = MockLLM(responses=['{"name": "Alice", "email": "alice@example.com"}'])
    memory = MEMORY()
    memory.add_msg("user", "Get user info", channel="api")
    
    keys_thought = THOUGHT(
        name="get_user",
        llm=mock_llm,
        prompt="Return user data",
        parser="json",
        validator="has_keys:name,email",  # Requires these keys
        channel="api"
    )
    
    memory = keys_thought(memory)
    result = memory.get_var("get_user_result")
    if result:
        print(f"has_keys validator passed: {result}")
    else:
        print(f"Validation failed: {keys_thought.last_error}")
    
    # Validator: list_min_len (check minimum list length)
    mock_llm = MockLLM(responses=["['task1', 'task2', 'task3']"])
    memory = MEMORY()
    memory.add_msg("user", "List tasks", channel="api")
    
    list_thought = THOUGHT(
        name="get_tasks",
        llm=mock_llm,
        prompt="Return task list",
        parser="list",
        validator="list_min_len:2",  # At least 2 items
        channel="api"
    )
    
    memory = list_thought(memory)
    result = memory.get_var("get_tasks_result")
    if result:
        print(f"list_min_len validator passed: {result}")
    else:
        print(f"Validation failed: {list_thought.last_error}")

    # =========================================================================
    # Part 6: Custom Validators
    # =========================================================================
    print("\n=== Part 6: Custom Validators ===\n")
    
    def validate_priority(result):
        """Custom validator that checks priority is 1-5."""
        if not isinstance(result, dict):
            return False, "Expected dict"
        priority = result.get("priority", 0)
        if 1 <= priority <= 5:
            return True, ""
        return False, f"Priority must be 1-5, got {priority}"
    
    mock_llm = MockLLM(responses=['{"task": "Review code", "priority": 3}'])
    memory = MEMORY()
    memory.add_msg("user", "Create task", channel="api")
    
    custom_thought = THOUGHT(
        name="create_task",
        llm=mock_llm,
        prompt="Create a task",
        parser="json",
        validation=validate_priority,  # Custom validation function
        channel="api"
    )
    
    memory = custom_thought(memory)
    result = memory.get_var("create_task_result")
    if result:
        print(f"Custom validator passed: {result}")
    else:
        print(f"Custom validation failed: {custom_thought.last_error}")

    # =========================================================================
    # Part 7: Retry Logic
    # =========================================================================
    print("\n=== Part 7: Retry Logic ===\n")
    
    # LLM that fails on first try, succeeds on second
    mock_llm = MockLLM(responses=[
        "Here's some invalid output without proper formatting",
        "['item1', 'item2', 'item3']"  # Valid on retry
    ])
    
    memory = MEMORY()
    memory.add_msg("user", "List items", channel="api")
    
    retry_thought = THOUGHT(
        name="retry_demo",
        llm=mock_llm,
        prompt="Return a list of items",
        parser="list",
        max_retries=3,        # Try up to 3 times
        retry_delay=0.1,      # Wait 0.1s between retries
        channel="api"
    )
    
    memory = retry_thought(memory)
    result = memory.get_var("retry_demo_result")
    
    print(f"LLM was called {mock_llm.call_count} times")
    print(f"Final result: {result}")
    print(f"Thought error: {retry_thought.last_error}")

    # =========================================================================
    # Part 8: Pre/Post Hooks
    # =========================================================================
    print("\n=== Part 8: Pre/Post Hooks ===\n")
    
    execution_log = []
    
    def my_pre_hook(thought, memory, vars, **kwargs):
        """Called before thought execution."""
        execution_log.append(f"PRE: Starting {thought.name}")
        # You can modify memory or vars here
        vars["injected_value"] = "from_pre_hook"
    
    def my_post_hook(thought, memory, result, error):
        """Called after thought execution."""
        if error:
            execution_log.append(f"POST: {thought.name} failed: {error}")
        else:
            execution_log.append(f"POST: {thought.name} succeeded")
    
    mock_llm = MockLLM(responses=["Hook demo response"])
    memory = MEMORY()
    memory.add_msg("user", "Test hooks", channel="api")
    
    hook_thought = THOUGHT(
        name="hook_demo",
        llm=mock_llm,
        prompt="Demo with hooks",
        pre_hook=my_pre_hook,
        post_hook=my_post_hook,
        channel="api"
    )
    
    memory = hook_thought(memory)
    
    print("Execution log from hooks:")
    for entry in execution_log:
        print(f"  {entry}")

    # =========================================================================
    # Part 9: Required and Optional Variables
    # =========================================================================
    print("\n=== Part 9: Required and Optional Variables ===\n")
    
    memory = MEMORY()
    memory.set_var("user_name", "Bob")
    memory.set_var("context", "Helpful assistant context")
    # Note: "preferences" is NOT set
    
    mock_llm = MockLLM(responses=["Hello Bob! Ready to assist."])
    
    # THOUGHT with variable requirements
    greet_thought = THOUGHT(
        name="greet_user",
        llm=mock_llm,
        prompt="Greet {user_name} using {context}. Consider {preferences} if available.",
        required_vars=["user_name", "context"],  # Must exist
        optional_vars=["preferences"],            # Nice to have
        channel="api"
    )
    
    # Check what context is available
    ctx = greet_thought.get_context(memory)
    print(f"Context built from memory:")
    print(f"  user_name: {ctx.get('user_name')}")
    print(f"  context: {ctx.get('context')}")
    print(f"  preferences: {ctx.get('preferences', 'NOT FOUND')}")
    
    memory = greet_thought(memory)
    print(f"\nResult: {memory.get_var('greet_user_result')}")

    # =========================================================================
    # Part 10: Execution History
    # =========================================================================
    print("\n=== Part 10: Execution History ===\n")
    
    mock_llm = MockLLM(responses=["Response 1", "Response 2", "Response 3"])
    memory = MEMORY()
    
    history_thought = THOUGHT(
        name="tracked",
        llm=mock_llm,
        prompt="Execute multiple times",
        channel="api"
    )
    
    # Execute multiple times
    for i in range(3):
        memory.add_msg("user", f"Request {i+1}", channel="api")
        memory = history_thought(memory)
    
    print(f"Total executions: {len(history_thought.execution_history)}")
    for i, record in enumerate(history_thought.execution_history):
        print(f"  Run {i+1}: success={record['success']}, duration={record['duration_ms']:.2f}ms")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n=== Summary ===")
    print("""
    Advanced THOUGHT features:
    
    1. Operations:
       - llm_call (default): Call LLM with prompt
       - memory_query: Read variables without LLM
       - variable_set: Set multiple variables
       - conditional: Branch based on conditions
    
    2. Parsing:
       - parsing_rules: Schema-based with valid_extract
       - parser: Built-in ('text', 'json', 'list')
       - parse_fn: Custom callable
    
    3. Validation:
       - validator: Built-in ('has_keys:k1,k2', 'list_min_len:N')
       - validation: Custom callable returning (bool, reason)
    
    4. Retry:
       - max_retries: Number of attempts
       - retry_delay: Seconds between retries
       - Automatic repair prompts on failure
    
    5. Hooks:
       - pre_hook: fn(thought, memory, vars, **kwargs)
       - post_hook: fn(thought, memory, result, error)
    
    6. Variables:
       - required_vars: Must exist in memory
       - optional_vars: Used if available
    """)


if __name__ == "__main__":
    main()

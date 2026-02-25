"""
Example 11: Action Primitives

This example demonstrates ThoughtFlow's 14 elemental ACTION primitives.
These actions are the fundamental "verbs" an agent uses to interact with the world.

All actions:
- Use only Python standard library (zero external dependencies)
- Follow the ACTION(memory) -> memory signature
- Support {variable} substitution from memory
- Log results to memory for traceability

Categories:
- Communication: SAY, ASK, NOTIFY
- Information Retrieval: SEARCH, FETCH, SCRAPE, READ
- Persistence: WRITE, POST
- Temporal Control: SLEEP, WAIT, NOOP
- Execution: RUN, CALL
"""

from thoughtflow import (
    MEMORY,
    # Action Primitives
    SAY, ASK, NOTIFY,           # Communication
    SEARCH, FETCH, SCRAPE, READ, # Information Retrieval
    WRITE, POST,                 # Persistence
    SLEEP, WAIT, NOOP,           # Temporal Control
    RUN, CALL,                   # Execution
)

# =============================================================================
# Example 1: Basic SAY Action
# =============================================================================

def example_say():
    """SAY outputs messages to the user."""
    print("\n=== Example 1: SAY Action ===")
    
    memory = MEMORY()
    memory.set_var("user_name", "Alice")
    
    # Simple message
    say_hello = SAY(message="Hello, {user_name}!")
    memory = say_hello(memory)
    
    # Styled message
    say_warning = SAY(message="This is a warning", style="warning")
    memory = say_warning(memory)
    
    # Output to memory instead of console
    say_to_memory = SAY(
        message="This goes to memory as assistant message",
        channel="memory"
    )
    memory = say_to_memory(memory)
    
    print("Assistant messages:", memory.get_msgs())


# =============================================================================
# Example 2: READ and WRITE Actions
# =============================================================================

def example_read_write():
    """READ and WRITE handle file I/O."""
    print("\n=== Example 2: READ/WRITE Actions ===")
    
    import tempfile
    import os
    
    memory = MEMORY()
    
    # Create a temp file path
    temp_path = os.path.join(tempfile.gettempdir(), "thoughtflow_example.json")
    
    # Write JSON data
    write_action = WRITE(
        name="save_config",
        path=temp_path,
        content={"name": "ThoughtFlow", "version": "0.0.7"},
        mode="json"
    )
    memory = write_action(memory)
    print(f"Write result: {memory.get_var('save_config_result')}")
    
    # Read it back
    read_action = READ(
        name="load_config",
        path=temp_path,
        parse="json"
    )
    memory = read_action(memory)
    print(f"Read result: {memory.get_var('load_config_content')}")
    
    # Cleanup
    os.unlink(temp_path)


# =============================================================================
# Example 3: SLEEP and NOOP Actions
# =============================================================================

def example_temporal():
    """SLEEP and NOOP control timing."""
    print("\n=== Example 3: SLEEP/NOOP Actions ===")
    
    import time
    memory = MEMORY()
    
    # NOOP - do nothing (useful for conditionals)
    enabled = False
    action = SAY(message="Feature active") if enabled else NOOP(reason="Feature disabled")
    memory = action(memory)
    
    if isinstance(action, NOOP):
        print(f"NOOP executed: {memory.get_var('noop_result')}")
    
    # SLEEP - pause execution
    print("Sleeping for 0.5 seconds...")
    start = time.time()
    sleep_action = SLEEP(duration=0.5, reason="Rate limit pause")
    memory = sleep_action(memory)
    print(f"Slept for {time.time() - start:.2f} seconds")


# =============================================================================
# Example 4: RUN Action (Shell Commands)
# =============================================================================

def example_run():
    """RUN executes shell commands."""
    print("\n=== Example 4: RUN Action ===")
    
    memory = MEMORY()
    
    # Simple command
    run_echo = RUN(command="echo 'Hello from shell!'")
    memory = run_echo(memory)
    result = memory.get_var("run_result")
    print(f"Command output: {result['stdout'].strip()}")
    print(f"Exit code: {result['return_code']}")
    
    # Command with variable substitution
    memory.set_var("greeting", "ThoughtFlow rocks!")
    run_var = RUN(command="echo '{greeting}'")
    memory = run_var(memory)
    print(f"Variable output: {memory.get_var('run_result')['stdout'].strip()}")


# =============================================================================
# Example 5: CALL Action (Function Invocation)
# =============================================================================

def example_call():
    """CALL invokes Python functions."""
    print("\n=== Example 5: CALL Action ===")
    
    memory = MEMORY()
    memory.set_var("numbers", [1, 2, 3, 4, 5])
    
    # Define a function
    def calculate_stats(numbers):
        return {
            "sum": sum(numbers),
            "avg": sum(numbers) / len(numbers),
            "count": len(numbers)
        }
    
    # Call it via CALL action
    call_action = CALL(
        name="stats",
        function=calculate_stats,
        params=lambda m: {"numbers": m.get_var("numbers")}
    )
    memory = call_action(memory)
    
    print(f"Stats result: {memory.get_var('stats_result')}")


# =============================================================================
# Example 6: WAIT Action (Condition Polling)
# =============================================================================

def example_wait():
    """WAIT polls until a condition is met."""
    print("\n=== Example 6: WAIT Action ===")
    
    import time
    import threading
    
    memory = MEMORY()
    memory.set_var("ready", False)
    
    # Simulate async completion
    def make_ready():
        time.sleep(0.3)
        memory.set_var("ready", True)
    
    thread = threading.Thread(target=make_ready)
    thread.start()
    
    # Wait for ready flag
    wait_action = WAIT(
        condition=lambda m: m.get_var("ready") == True,
        timeout=5,
        poll_interval=0.1
    )
    
    print("Waiting for ready flag...")
    memory = wait_action(memory)
    result = memory.get_var("wait_result")
    print(f"Wait completed: {result['status']} after {result['waited_seconds']}s")
    
    thread.join()


# =============================================================================
# Example 7: NOTIFY Action (Notifications)
# =============================================================================

def example_notify():
    """NOTIFY sends notifications via console or webhook."""
    print("\n=== Example 7: NOTIFY Action ===")
    
    memory = MEMORY()
    memory.set_var("task_name", "data processing")
    
    # Console notification
    notify = NOTIFY(
        method="console",
        body="Task '{task_name}' completed successfully!"
    )
    memory = notify(memory)


# =============================================================================
# Example 8: Chaining Actions
# =============================================================================

def example_chaining():
    """Actions can be chained together."""
    print("\n=== Example 8: Chaining Actions ===")
    
    import tempfile
    import os
    
    memory = MEMORY()
    temp_path = os.path.join(tempfile.gettempdir(), "thoughtflow_chain.txt")
    
    # Set up initial data
    memory.set_var("output_path", temp_path)
    memory.set_var("message", "Hello from chained actions!")
    
    # Chain: SAY -> WRITE -> READ -> SAY
    actions = [
        SAY(message="Step 1: Processing..."),
        WRITE(
            name="save",
            path="{output_path}",
            content="{message}"
        ),
        READ(
            name="load",
            path="{output_path}"
        ),
        SAY(message="Step 4: Read content: {load_content}"),
    ]
    
    # Execute chain
    for action in actions:
        memory = action(memory)
    
    # Cleanup
    os.unlink(temp_path)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("ThoughtFlow Action Primitives Demo")
    print("=" * 50)
    
    example_say()
    example_read_write()
    example_temporal()
    example_run()
    example_call()
    example_wait()
    example_notify()
    example_chaining()
    
    print("\n" + "=" * 50)
    print("All examples completed!")

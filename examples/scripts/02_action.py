#!/usr/bin/env python3
"""
ThoughtFlow Example 02: ACTION - External Operations

Demonstrates how to use the ACTION class to wrap external operations
(API calls, database queries, file operations, etc.) with consistent
logging, error handling, and result storage.

Prerequisites:
    pip install thoughtflow

Run:
    python examples/02_action.py
"""

import json
from thoughtflow import MEMORY, ACTION


# --- Define Functions to Wrap as ACTIONs ---

def fetch_weather(memory, location="Unknown", units="F"):
    """Simulate fetching weather data from an API."""
    # In a real app, this would call a weather API
    weather_data = {
        "San Francisco, CA": {"temp": 65, "condition": "foggy"},
        "New York, NY": {"temp": 45, "condition": "cloudy"},
        "Miami, FL": {"temp": 82, "condition": "sunny"},
    }
    
    data = weather_data.get(location, {"temp": 70, "condition": "unknown"})
    return {
        "location": location,
        "temperature": data["temp"],
        "units": units,
        "condition": data["condition"],
    }


def calculate(memory, expression):
    """Evaluate a mathematical expression."""
    # WARNING: eval is dangerous in production! Use a safe math parser.
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result, "success": True}
    except Exception as e:
        return {"expression": expression, "error": str(e), "success": False}


def save_note(memory, title, content):
    """Simulate saving a note to storage."""
    # In a real app, this would save to a database
    note_id = f"note_{hash(title) % 10000:04d}"
    return {
        "id": note_id,
        "title": title,
        "content": content,
        "saved": True,
    }


def failing_action(memory):
    """An action that always fails (for error handling demo)."""
    raise ConnectionError("Simulated network failure")


def main():
    print("--- ThoughtFlow ACTION Demo ---\n")
    
    # Create a MEMORY instance
    memory = MEMORY()

    # =========================================================================
    # Part 1: Creating and Executing ACTIONs
    # =========================================================================
    print("=== Part 1: Basic ACTION Usage ===\n")
    
    # Create an ACTION from a function
    weather_action = ACTION(
        name="get_weather",
        fn=fetch_weather,
        config={"location": "San Francisco, CA", "units": "F"},
        description="Fetch current weather for a location"
    )
    
    print(f"Created ACTION: {weather_action.name}")
    print(f"  ID: {weather_action.id}")
    print(f"  Description: {weather_action.description}")
    
    # Execute the action - it receives memory and returns memory
    memory = weather_action(memory)
    
    # Results are automatically stored in memory
    result = memory.get_var("get_weather_result")
    print(f"\nWeather result (stored in memory):")
    print(f"  Location: {result['location']}")
    print(f"  Temperature: {result['temperature']}°{result['units']}")
    print(f"  Condition: {result['condition']}")

    # =========================================================================
    # Part 2: Overriding Config at Call Time
    # =========================================================================
    print("\n=== Part 2: Overriding Config ===\n")
    
    # Override the default location at call time
    memory = weather_action(memory, location="Miami, FL")
    result = memory.get_var("get_weather_result")
    print(f"Miami weather: {result['temperature']}°{result['units']}, {result['condition']}")

    # =========================================================================
    # Part 3: Execution History and Stats
    # =========================================================================
    print("\n=== Part 3: Execution History ===\n")
    
    print(f"Execution count: {weather_action.execution_count}")
    print(f"Was successful: {weather_action.was_successful()}")
    print(f"Last result: {weather_action.last_result}")
    
    print("\nFull execution history:")
    for i, record in enumerate(weather_action.execution_history):
        print(f"  Run {i+1}:")
        print(f"    Success: {record['success']}")
        print(f"    Duration: {record['duration_ms']:.2f}ms")
        print(f"    Timestamp: {record['stamp'][:12]}...")

    # =========================================================================
    # Part 4: Error Handling
    # =========================================================================
    print("\n=== Part 4: Error Handling ===\n")
    
    # Create an action that will fail
    risky_action = ACTION(
        name="risky_operation",
        fn=failing_action,
        description="An operation that might fail"
    )
    
    # Execute it - errors are caught and logged, not raised
    memory = risky_action(memory)
    
    print(f"Was successful: {risky_action.was_successful()}")
    print(f"Last error: {risky_action.last_error}")
    
    # The error is also stored in memory
    result = memory.get_var("risky_operation_result")
    print(f"Result stored: {result}")  # None when error occurs

    # =========================================================================
    # Part 5: Custom Result Key
    # =========================================================================
    print("\n=== Part 5: Custom Result Key ===\n")
    
    # Store result under a custom variable name
    calc_action = ACTION(
        name="calculator",
        fn=calculate,
        result_key="calculation_output",  # Custom key instead of "calculator_result"
        description="Evaluate math expressions"
    )
    
    memory = calc_action(memory, expression="15 * 7 + 3")
    result = memory.get_var("calculation_output")
    print(f"Expression: {result['expression']}")
    print(f"Result: {result['result']}")

    # =========================================================================
    # Part 6: Memory Logs (Automatic Tracking)
    # =========================================================================
    print("\n=== Part 6: Automatic Logging ===\n")
    
    print("ACTION executions are automatically logged to memory:")
    for log in memory.get_logs(limit=5):
        # Parse the JSON log content
        try:
            log_data = json.loads(log['content'])
            print(f"  [{log_data.get('action', 'unknown')}] success={log_data.get('success')}")
        except json.JSONDecodeError:
            print(f"  {log['content'][:60]}...")

    # =========================================================================
    # Part 7: Serialization
    # =========================================================================
    print("\n=== Part 7: Serialization ===\n")
    
    # Serialize an ACTION to dict (for saving/loading)
    action_dict = weather_action.to_dict()
    print("ACTION serialized to dict:")
    print(f"  name: {action_dict['name']}")
    print(f"  config: {action_dict['config']}")
    print(f"  execution_count: {action_dict['execution_count']}")
    
    # Note: to_dict() excludes the function reference
    # Use from_dict() with a function registry to restore
    print("\nNote: Use from_dict(data, fn_registry) to restore ACTIONs")
    
    fn_registry = {"get_weather": fetch_weather}
    restored_action = ACTION.from_dict(action_dict, fn_registry)
    print(f"Restored ACTION: {restored_action.name}")

    # =========================================================================
    # Part 8: Copying and Resetting
    # =========================================================================
    print("\n=== Part 8: Copy and Reset ===\n")
    
    # Create a fresh copy with reset stats
    fresh_action = weather_action.copy()
    print(f"Original execution count: {weather_action.execution_count}")
    print(f"Copy execution count: {fresh_action.execution_count}")
    print(f"Copy has new ID: {fresh_action.id != weather_action.id}")
    
    # Or reset stats on the original
    weather_action.reset_stats()
    print(f"After reset: {weather_action.execution_count}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n=== Summary ===")
    print("""
    ACTION wraps external operations with:
    
    1. Consistent interface: memory = action(memory, **kwargs)
    2. Automatic result storage: memory.get_var("{name}_result")
    3. Error handling: Errors logged, not raised
    4. Execution tracking: count, history, timing
    5. Serialization: to_dict() / from_dict()
    
    Use ACTION for any external operation:
    - API calls
    - Database queries
    - File operations
    - External tool invocations
    """)


if __name__ == "__main__":
    main()

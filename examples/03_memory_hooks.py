#!/usr/bin/env python3
"""
ThoughtFlow Example 03: MEMORY Usage

Demonstrates the MEMORY class for managing conversation state,
variables, logs, and reflections.

Prerequisites:
    pip install thoughtflow

Run:
    python examples/03_memory_hooks.py
"""

from thoughtflow import MEMORY


def main():
    # Create a MEMORY instance
    memory = MEMORY()
    print(f"Memory ID: {memory.id}")

    # --- Adding Messages with Channels ---
    print("\n--- Adding Messages ---")
    memory.add_msg("system", "You are a helpful assistant.", channel="webapp")
    memory.add_msg("user", "My name is Alice and I'm a software engineer.", channel="webapp")
    memory.add_msg("assistant", "Nice to meet you, Alice! How can I help you today?", channel="webapp")
    
    print("Messages added:")
    for msg in memory.get_msgs():
        print(f"  [{msg['role']}] {msg['content'][:50]}...")

    # --- Setting Variables ---
    print("\n--- Setting Variables ---")
    memory.set_var("user_name", "Alice", desc="User's name")
    memory.set_var("occupation", "software engineer", desc="User's job title")
    memory.set_var("preferences", {"language": "Python", "framework": "FastAPI"}, desc="User preferences")
    
    print("Variables set:")
    print(f"  user_name: {memory.get_var('user_name')}")
    print(f"  occupation: {memory.get_var('occupation')}")
    print(f"  preferences: {memory.get_var('preferences')}")

    # --- Variable History ---
    print("\n--- Variable History (Updating Variables) ---")
    memory.set_var("preferences", {"language": "Python", "framework": "Django"})  # Update
    memory.set_var("preferences", {"language": "Python", "framework": "Flask"})   # Update again
    
    print("Preference history:")
    for stamp, value in memory.get_var_history("preferences"):
        print(f"  {stamp[:10]}... -> {value}")

    # --- Logs and Reflections ---
    print("\n--- Logs and Reflections ---")
    memory.add_log("User started a new session")
    memory.add_log("User mentioned their background in software")
    memory.add_ref("User seems experienced in Python development")
    memory.add_ref("User is exploring different web frameworks")
    
    print("Logs:")
    for log in memory.get_logs():
        print(f"  {log['content']}")
    
    print("\nReflections:")
    for ref in memory.get_refs():
        print(f"  {ref['content']}")

    # --- Prepare Context for LLM ---
    print("\n--- Preparing Context for LLM ---")
    context = memory.prepare_context(
        recent_count=3,
        format='openai'
    )
    print("Context messages for LLM:")
    for msg in context:
        content_preview = msg['content'][:60] + "..." if len(msg['content']) > 60 else msg['content']
        print(f"  {msg['role']}: {content_preview}")

    # --- Render Memory State ---
    print("\n--- Render as Conversation ---")
    print(memory.render(output_format='conversation', max_total_length=500))

    # --- Get All Variables ---
    print("\n--- All Variables ---")
    all_vars = memory.get_all_vars()
    for key, value in all_vars.items():
        print(f"  {key}: {value}")

    # --- Variable Deletion ---
    print("\n--- Variable Deletion ---")
    memory.del_var("occupation")
    print(f"occupation after deletion: {memory.get_var('occupation')}")
    print(f"is_var_deleted('occupation'): {memory.is_var_deleted('occupation')}")
    
    # Can re-set after deletion
    memory.set_var("occupation", "tech lead")
    print(f"occupation after re-setting: {memory.get_var('occupation')}")

    # --- Save/Load State ---
    print("\n--- Save/Load State ---")
    # Save to JSON
    json_str = memory.to_json()
    print(f"JSON export length: {len(json_str)} chars")
    
    # Create new memory from JSON
    memory2 = MEMORY.from_json(json_str)
    print(f"Loaded memory ID: {memory2.id}")
    print(f"Loaded user_name: {memory2.get_var('user_name')}")

    # --- Snapshot for Cloud Sync ---
    print("\n--- Snapshot (for cloud sync) ---")
    snapshot = memory.snapshot()
    print(f"Snapshot keys: {list(snapshot.keys())}")
    print(f"Event count: {len(snapshot['events'])}")
    
    # Rehydrate from events
    memory3 = MEMORY.from_events(snapshot['events'].values(), memory.id)
    print(f"Rehydrated memory has {len(memory3.events)} events")


if __name__ == "__main__":
    main()

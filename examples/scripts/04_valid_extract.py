#!/usr/bin/env python3
"""
ThoughtFlow Example 04: valid_extract - Parsing LLM Outputs

Demonstrates how to use the valid_extract utility to reliably parse
and validate structured data from LLM outputs. LLMs often include
extra prose, code fences, or formatting - valid_extract handles all of this.

Prerequisites:
    pip install thoughtflow

Run:
    python examples/04_valid_extract.py
"""

from thoughtflow import valid_extract, ValidExtractError


def main():
    print("--- ThoughtFlow valid_extract Demo ---\n")

    # =========================================================================
    # Part 1: Basic List Extraction
    # =========================================================================
    print("=== Part 1: Extracting Lists ===\n")
    
    # LLM output with extra prose and code fences
    llm_output = """
    Sure! Here's the list of prime numbers you asked for:
    
    ```python
    [2, 3, 5, 7, 11, 13]
    ```
    
    These are the first six prime numbers. Let me know if you need more!
    """
    
    # Define parsing rules: we want a list
    rules = {
        "kind": "python",  # Parse as Python literal
        "format": []       # Expect a list (any contents)
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Input: {llm_output[:50]}...")
    print(f"Extracted: {result}")
    print(f"Type: {type(result).__name__}")

    # =========================================================================
    # Part 2: Extracting Dictionaries
    # =========================================================================
    print("\n=== Part 2: Extracting Dictionaries ===\n")
    
    llm_output = """
    Based on my analysis, here's the user profile:
    
    {'name': 'Alice', 'age': 28, 'skills': ['Python', 'ML', 'Data Science']}
    
    This profile shows an experienced data professional.
    """
    
    # Extract any dict
    rules = {"kind": "python", "format": {}}
    result = valid_extract(llm_output, rules)
    print(f"Extracted dict: {result}")

    # =========================================================================
    # Part 3: Schema Validation with Required Keys
    # =========================================================================
    print("\n=== Part 3: Schema Validation (Required Keys) ===\n")
    
    llm_output = """
    Here's the task breakdown:
    
    ```python
    {
        'task_name': 'Deploy Application',
        'priority': 1,
        'subtasks': ['Build', 'Test', 'Deploy']
    }
    ```
    """
    
    # Schema with required keys and their types
    rules = {
        "kind": "python",
        "format": {
            "task_name": "",       # Required string ('' = str type)
            "priority": 0,         # Required int (0 = int type)
            "subtasks": []         # Required list
        }
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Task: {result['task_name']}")
    print(f"Priority: {result['priority']}")
    print(f"Subtasks: {result['subtasks']}")

    # =========================================================================
    # Part 4: Optional Keys
    # =========================================================================
    print("\n=== Part 4: Optional Keys (key?) ===\n")
    
    llm_output = "{'name': 'Bob', 'email': 'bob@example.com'}"
    
    # Use '?' suffix for optional keys
    rules = {
        "kind": "python",
        "format": {
            "name": "",           # Required
            "email": "",          # Required
            "phone?": "",         # Optional - won't fail if missing
            "address?": ""        # Optional
        }
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Name: {result['name']}")
    print(f"Email: {result['email']}")
    print(f"Has phone: {'phone' in result}")  # False - it was optional and missing

    # =========================================================================
    # Part 5: Nested Structures
    # =========================================================================
    print("\n=== Part 5: Nested Structures ===\n")
    
    llm_output = """
    {
        'user': {
            'id': 123,
            'profile': {
                'name': 'Charlie',
                'settings': {'theme': 'dark', 'notifications': True}
            }
        },
        'metadata': {'version': '1.0'}
    }
    """
    
    rules = {
        "kind": "python",
        "format": {
            "user": {
                "id": 0,
                "profile": {
                    "name": "",
                    "settings": {}  # Any dict for settings
                }
            },
            "metadata": {}
        }
    }
    
    result = valid_extract(llm_output, rules)
    print(f"User ID: {result['user']['id']}")
    print(f"User Name: {result['user']['profile']['name']}")
    print(f"Theme: {result['user']['profile']['settings']['theme']}")

    # =========================================================================
    # Part 6: List Element Validation
    # =========================================================================
    print("\n=== Part 6: List Element Validation ===\n")
    
    llm_output = """
    ```python
    [
        {'id': 1, 'name': 'Task A', 'done': False},
        {'id': 2, 'name': 'Task B', 'done': True},
        {'id': 3, 'name': 'Task C', 'done': False}
    ]
    ```
    """
    
    # [schema] means every element must match schema
    rules = {
        "kind": "python",
        "format": [{  # List where each element matches this dict schema
            "id": 0,
            "name": "",
            "done": True  # bool type
        }]
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Found {len(result)} tasks:")
    for task in result:
        status = "Done" if task['done'] else "Pending"
        print(f"  [{status}] {task['name']}")

    # =========================================================================
    # Part 7: JSON Parsing
    # =========================================================================
    print("\n=== Part 7: JSON Parsing ===\n")
    
    llm_output = '''
    Here's the JSON response:
    
    ```json
    {"status": "success", "data": [1, 2, 3], "count": 3}
    ```
    '''
    
    rules = {
        "kind": "json",  # Parse as JSON
        "format": {
            "status": "",
            "data": [],
            "count": 0
        }
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Status: {result['status']}")
    print(f"Data: {result['data']}")

    # =========================================================================
    # Part 8: Error Handling
    # =========================================================================
    print("\n=== Part 8: Error Handling ===\n")
    
    # Case 1: Missing required key
    llm_output = "{'name': 'Alice'}"  # Missing 'age'
    rules = {
        "kind": "python",
        "format": {"name": "", "age": 0}  # Both required
    }
    
    try:
        result = valid_extract(llm_output, rules)
    except ValidExtractError as e:
        print(f"Error (missing key): {e}")
    
    # Case 2: Wrong type
    llm_output = "{'count': 'five'}"  # String instead of int
    rules = {"kind": "python", "format": {"count": 0}}
    
    try:
        result = valid_extract(llm_output, rules)
    except ValidExtractError as e:
        print(f"Error (wrong type): {e}")
    
    # Case 3: No parseable content
    llm_output = "I don't have any structured data to provide."
    rules = {"kind": "python", "format": []}
    
    try:
        result = valid_extract(llm_output, rules)
    except ValidExtractError as e:
        print(f"Error (no data): {e}")

    # =========================================================================
    # Part 9: Type Exemplars
    # =========================================================================
    print("\n=== Part 9: Type Exemplars ===\n")
    
    print("Schema type mapping:")
    print("  '' or str   -> string")
    print("  0 or int    -> integer")
    print("  0.0 or float -> float")
    print("  True or bool -> boolean")
    print("  None        -> NoneType")
    print("  []          -> list (any contents)")
    print("  [schema]    -> list of items matching schema")
    print("  {}          -> dict (any contents)")
    print("  {'k': sch}  -> dict with required key 'k'")
    print("  {'k?': sch} -> dict with optional key 'k'")

    # =========================================================================
    # Part 10: Real-World Pattern - Structured LLM Output
    # =========================================================================
    print("\n=== Part 10: Real-World Pattern ===\n")
    
    # Simulated LLM response for a "analyze sentiment" task
    llm_output = """
    I've analyzed the text for sentiment. Here are my findings:
    
    ```python
    {
        'sentiment': 'positive',
        'confidence': 0.87,
        'keywords': ['excellent', 'wonderful', 'recommend'],
        'entities': [
            {'text': 'product', 'type': 'ITEM'},
            {'text': 'customer service', 'type': 'SERVICE'}
        ]
    }
    ```
    
    The text shows strong positive sentiment with high confidence.
    """
    
    rules = {
        "kind": "python",
        "format": {
            "sentiment": "",
            "confidence": 0.0,
            "keywords": [""],  # List of strings
            "entities": [{     # List of entity dicts
                "text": "",
                "type": ""
            }]
        }
    }
    
    result = valid_extract(llm_output, rules)
    print(f"Sentiment: {result['sentiment']}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"Keywords: {', '.join(result['keywords'])}")
    print(f"Entities found: {len(result['entities'])}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n=== Summary ===")
    print("""
    valid_extract() reliably parses structured data from LLM output:
    
    1. Handles code fences: ```python ... ``` or ```json ... ```
    2. Extracts balanced structures: {...} or [...]
    3. Validates against schemas with type checking
    4. Supports optional keys with '?' suffix
    5. Works with nested structures
    6. Raises ValidExtractError on failure
    
    Usage pattern:
        rules = {'kind': 'python', 'format': expected_schema}
        result = valid_extract(llm_output, rules)
    """)


if __name__ == "__main__":
    main()

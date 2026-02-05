# Writing Tests

This guide explains how to write effective tests for ThoughtFlow.

**Important**: All tests use only Python standard library for test logic. The only external dependency is `pytest` itself. No additional test frameworks or external imports are required.

---

## Test Docstring Requirements

Every test in ThoughtFlow **must** have a docstring that explains:

1. **WHAT** - What behavior is being tested
2. **WHY** - Why this test exists (what breaks if this fails)
3. **REMOVAL** - When this test should be removed

### Template

```python
def test_example():
    """
    [WHAT] Brief description of behavior being tested.
    
    [WHY] This test exists because... (explain the importance)
    
    [REMOVAL] Remove this test if/when... (future guidance)
    """
```

### Examples

```python
def test_stamps_are_chronologically_sortable(self):
    """
    EventStamp IDs must be sortable alphabetically such that 
    alphabetical order equals chronological order.
    
    This is a CRITICAL invariant that enables efficient event ordering
    without decoding timestamps. Database indexes depend on this property.
    
    Remove this test if: We change the stamp format (breaking change).
    """

def test_memory_rehydrates_from_events(self):
    """
    MEMORY must be fully reconstructable from its event list.
    
    This is the core event-sourcing invariant that enables:
    - Cloud sync (send events, rebuild state)
    - Debugging (replay exact state)
    - Portability (serialize/deserialize)
    
    Remove this test if: We abandon event-sourcing architecture.
    """

def test_thought_is_callable(self):
    """
    THOUGHT must support: mem = thought(mem)
    
    This callable interface is the CORE contract of the class.
    All agent workflows depend on this pattern.
    
    Remove this test if: We change the THOUGHT interface (major version).
    """
```

---

## Test File Structure

### File Naming

```
tests/
├── unit/
│   └── test_<module_name>.py    # e.g., test_memory.py, test_thought.py
└── integration/
    └── test_<provider>_*.py     # e.g., test_llm_providers.py
```

### Test Organization

Group tests by behavior using test classes:

```python
# tests/unit/test_memory.py

class TestMemoryInitialization:
    """Tests for MEMORY initialization and setup."""

    def test_creates_unique_id(self, memory):
        """Each MEMORY must have a unique ID..."""
        pass

    def test_starts_with_empty_state(self, memory):
        """New MEMORY instances must start empty..."""
        pass


class TestMessageOperations:
    """Tests for message-related MEMORY operations."""

    def test_add_msg_stores_message(self, memory):
        """add_msg must store retrievable messages..."""
        pass


class TestSerialization:
    """Tests for MEMORY serialization/deserialization."""

    def test_snapshot_captures_state(self, memory):
        """snapshot must capture complete state..."""
        pass
```

---

## Test Naming Convention

Format: `test_<what>_<condition>_<expected_behavior>`

**Good names:**
```python
def test_memory_add_msg_with_invalid_role_raises_error(self):
def test_thought_retry_with_parse_failure_includes_repair_prompt(self):
def test_action_execution_with_error_logs_to_memory(self):
def test_stamps_generated_concurrently_are_unique(self):
```

**Bad names:**
```python
def test_1(self):
def test_memory(self):
def test_it_works(self):
def test_happy_path(self):
```

---

## Testing ThoughtFlow Primitives

### Testing MEMORY

Use the `memory` fixture for fresh instances:

```python
def test_variable_history_preserved(self, memory):
    """
    set_var must append to history, not overwrite.
    
    This enables audit trails and undo operations.
    
    Remove this test if: We implement hard overwrites.
    """
    memory.set_var('x', 1)
    memory.set_var('x', 2)
    memory.set_var('x', 3)
    
    history = memory.get_var_history('x')
    values = [h[1] for h in history]
    
    assert values == [1, 2, 3]
```

### Testing THOUGHT (with MockLLM)

Always use `MockLLM` for unit tests - never make real API calls:

```python
def test_thought_stores_result_in_output_var(self, mock_llm, memory):
    """
    THOUGHT must store the LLM result in output_var when specified.
    
    This enables accessing results via memory.get_var().
    
    Remove this test if: We change output storage mechanism.
    """
    llm = mock_llm(responses=["Hello, I'm the LLM!"])
    thought = THOUGHT(
        name="test",
        llm=llm,
        prompt="Hello",
        output_var="greeting",
    )
    
    thought(memory)
    
    assert memory.get_var("greeting") == "Hello, I'm the LLM!"
```

### Testing THOUGHT Retry Logic

```python
def test_retry_on_parse_failure(self, mock_llm, memory):
    """
    THOUGHT must retry when parsing fails.
    
    LLMs sometimes produce invalid output that needs correction.
    
    Remove this test if: We remove retry logic.
    """
    # First response is invalid, second is valid
    llm = mock_llm(responses=[
        "Not valid JSON",
        '{"value": 42}',
    ])
    thought = THOUGHT(
        name="test",
        llm=llm,
        prompt="Give me JSON",
        output_var="result",
        parse='json',
        max_retries=2,
    )
    
    thought(memory)
    
    assert llm.call_count == 2
    assert memory.get_var("result") == {"value": 42}
```

### Testing ACTION

```python
def test_action_logs_execution(self, memory):
    """
    ACTION must log its execution to memory.
    
    Logs enable debugging and audit trails.
    
    Remove this test if: We remove execution logging.
    """
    action = ACTION(name="test_action", fn=lambda: "ok")
    action(memory)
    
    logs = memory.get_logs()
    log_content = ' '.join(l['content'] for l in logs)
    
    assert 'test_action' in log_content.lower() or len(logs) > 0
```

---

## Mock LLM Usage Patterns

### Basic Mock

```python
def test_basic_call(self, mock_llm, memory):
    llm = mock_llm(responses=["Response"])
    # Use llm...
```

### Multiple Responses (for retry testing)

```python
def test_retry_scenario(self, mock_llm, memory):
    llm = mock_llm(responses=[
        "Invalid first response",
        '{"valid": true}',  # Will be used on retry
    ])
```

### Verifying Call Arguments

```python
def test_prompt_sent_correctly(self, mock_llm, memory):
    llm = mock_llm(responses=["Response"])
    thought = THOUGHT(name="t", llm=llm, prompt="My prompt")
    
    thought(memory)
    
    # Verify what was sent to the LLM
    last_call = llm.calls[-1]
    msgs = last_call['msgs']
    assert any('My prompt' in str(m.get('content', '')) for m in msgs)
```

### Checking Call Count

```python
def test_no_llm_call_for_memory_query(self, mock_llm, memory):
    llm = mock_llm()
    thought = THOUGHT(
        name="query",
        operation="memory_query",
        query_vars=['x'],
        llm=llm,  # Provided but shouldn't be used
    )
    
    thought(memory)
    
    assert llm.call_count == 0  # Should not have called LLM
```

---

## Testing Patterns

### Arrange-Act-Assert

```python
def test_message_to_dict(self, memory):
    """Message retrieval should return proper dict format."""
    # Arrange - Set up test data
    memory.add_msg('user', 'Hello!', channel='webapp')
    
    # Act - Perform the action
    msgs = memory.get_msgs()
    
    # Assert - Verify the result
    assert msgs[0]['role'] == 'user'
    assert msgs[0]['content'] == 'Hello!'
```

### Testing Exceptions

```python
def test_invalid_role_raises_error(self, memory):
    """
    add_msg must reject invalid roles.
    
    This prevents issues with LLM APIs that expect specific roles.
    
    Remove this test if: We remove role validation.
    """
    with pytest.raises(ValueError, match="Invalid role"):
        memory.add_msg('invalid_role', 'Content', channel='webapp')
```

### Testing Side Effects

```python
def test_action_increments_exec_count(self, memory):
    """
    ACTION must track execution count.
    
    This enables monitoring and rate limiting.
    
    Remove this test if: We remove execution tracking.
    """
    action = ACTION(name="counter", fn=lambda: "ok")
    
    assert action.exec_count == 0
    action(memory)
    assert action.exec_count == 1
    action(memory)
    assert action.exec_count == 2
```

---

## Parameterized Tests

Test multiple inputs efficiently:

```python
@pytest.mark.parametrize("role", ["user", "assistant", "system"])
def test_accepts_valid_roles(self, memory, role):
    """MEMORY should accept all valid message roles."""
    memory.add_msg(role, "content", channel="webapp")
    assert memory.get_msgs()[0]['role'] == role

@pytest.mark.parametrize("parse_mode,input_text,expected", [
    ('text', 'Hello', 'Hello'),
    ('json', '{"x": 1}', {'x': 1}),
    ('list', '[1, 2, 3]', [1, 2, 3]),
])
def test_parse_modes(self, mock_llm, memory, parse_mode, input_text, expected):
    """THOUGHT should parse different formats correctly."""
    llm = mock_llm(responses=[input_text])
    thought = THOUGHT(name="t", llm=llm, prompt="", output_var="r", parse=parse_mode)
    thought(memory)
    assert memory.get_var("r") == expected
```

---

## Integration Tests

Integration tests require real API keys and are skipped by default.

### Setup

```python
# tests/integration/test_llm_providers.py

import os
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled. Set THOUGHTFLOW_INTEGRATION_TESTS=1",
    ),
]

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestOpenAIIntegration:
    def test_basic_completion(self):
        """
        Verify LLM can make a real OpenAI API call.
        
        This validates HTTP request formatting and response parsing.
        
        Remove this test if: OpenAI changes their API significantly.
        """
        llm = LLM(model="openai:gpt-4o-mini", key=os.getenv("OPENAI_API_KEY"))
        result = llm.call("What is 2+2? Reply with just the number.", {"max_tokens": 10})
        assert "4" in result[0]
```

---

## What NOT to Test

### Don't test private methods

```python
# Don't do this:
def test_internal_helper(self, memory):
    result = memory._internal_helper()  # Testing private method

# Do this instead:
def test_public_method_uses_helper_correctly(self, memory):
    memory.add_msg('user', 'Hello', channel='webapp')
    # Assert the overall behavior is correct
```

### Don't test exact LLM output

```python
# Don't do this (non-deterministic):
def test_llm_response(self):
    result = llm.call("Hello")
    assert result == "Hello there!"  # LLM output varies

# Do this instead:
def test_llm_response_structure(self, mock_llm, memory):
    llm = mock_llm(responses=["Expected response"])
    # Test your code's handling of the response
```

### Don't test implementation details

```python
# Don't do this:
def test_memory_uses_dict_internally(self, memory):
    assert isinstance(memory._internal_store, dict)

# Do this instead:
def test_memory_stores_and_retrieves(self, memory):
    memory.set_var('x', 1)
    assert memory.get_var('x') == 1
```

---

## Checklist for New Tests

- [ ] Test is in correct directory (unit vs integration)
- [ ] Test file named `test_<module>.py`
- [ ] Test has a descriptive name following `test_<what>_<condition>_<expected>`
- [ ] Test has a docstring with WHAT, WHY, and REMOVAL guidance
- [ ] Test follows Arrange-Act-Assert pattern
- [ ] Test is independent (no shared state between tests)
- [ ] Test is deterministic (same result every time)
- [ ] Test runs quickly (< 1 second for unit tests)
- [ ] Test uses fixtures for common setup
- [ ] Test uses MockLLM instead of real API calls (for unit tests)
- [ ] Test uses only Python standard library (no external imports)

---

## Common Assertions

```python
# Equality
assert result == expected

# Truth
assert condition
assert not condition

# Containment
assert item in collection
assert "substring" in string

# Type
assert isinstance(result, MEMORY)

# Length
assert len(items) == 3

# Identity
assert result is None
assert result is not None

# Approximate equality (floats)
assert result == pytest.approx(3.14, rel=0.01)

# Exception
with pytest.raises(ValueError):
    do_something()

with pytest.raises(ValueError, match="expected message"):
    do_something()
```

---

## Running Your Tests

```bash
# Run specific test file
pytest tests/unit/test_memory.py -v

# Run specific test class
pytest tests/unit/test_memory.py::TestMemoryInitialization -v

# Run specific test
pytest tests/unit/test_memory.py::TestMemoryInitialization::test_creates_unique_id -v

# Run with print output
pytest tests/unit/test_memory.py -v -s

# Run and stop on first failure
pytest tests/unit/test_memory.py -v -x

# Run with coverage
pytest tests/unit/test_memory.py --cov=src/thoughtflow/memory
```

---

## Next Steps

- [06-running-tests.md](06-running-tests.md) - Run your tests
- [13-adding-features.md](13-adding-features.md) - Add features with tests

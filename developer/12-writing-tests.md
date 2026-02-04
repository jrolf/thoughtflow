# Writing Tests

This guide explains how to write effective tests for ThoughtFlow.

---

## Test Structure

### File Naming

```
tests/
├── unit/
│   └── test_<module_name>.py
└── integration/
    └── test_<adapter>_adapter.py
```

### Test Organization

```python
# tests/unit/test_agent.py

class TestAgent:
    """Tests for the Agent class."""

    def test_something(self):
        """Agent should do something."""
        pass

class TestTracedAgent:
    """Tests for the TracedAgent wrapper."""

    def test_something_else(self):
        """TracedAgent should do something else."""
        pass
```

---

## Anatomy of a Test

```python
def test_message_to_dict_includes_role_and_content(self) -> None:
    """Message.to_dict() should return dict with role and content."""
    # Arrange - Set up test data
    msg = Message(role="user", content="Hello!")

    # Act - Perform the action
    result = msg.to_dict()

    # Assert - Verify the result
    assert result == {"role": "user", "content": "Hello!"}
```

### Test Naming

Format: `test_<what>_<condition>_<expected>`

Good names:
```python
def test_agent_call_with_empty_messages_raises_error(self):
def test_message_from_dict_handles_optional_fields(self):
def test_session_add_event_increments_count(self):
```

Bad names:
```python
def test_1(self):
def test_agent(self):
def test_it_works(self):
```

---

## Using Fixtures

Fixtures provide reusable test data and setup.

### Built-in Fixtures

From `tests/conftest.py`:

```python
def test_with_sample_messages(self, sample_messages):
    """Use the sample_messages fixture."""
    assert len(sample_messages) == 2
    assert sample_messages[0]["role"] == "system"

def test_with_mock_adapter(self, mock_adapter):
    """Use the mock_adapter fixture."""
    agent = Agent(mock_adapter)
    # mock_adapter.calls tracks all calls made
```

### Creating Fixtures

```python
# tests/conftest.py

@pytest.fixture
def sample_tool():
    """Create a sample tool for testing."""
    class SampleTool(Tool):
        name = "sample"
        description = "A sample tool"

        def call(self, payload, params=None):
            return ToolResult.ok(output="result")

    return SampleTool()

@pytest.fixture
def empty_registry():
    """Create an empty tool registry."""
    return ToolRegistry()
```

### Fixture Scope

```python
@pytest.fixture(scope="function")  # Default: new instance per test
def per_test_fixture():
    return SomeObject()

@pytest.fixture(scope="class")  # Shared within test class
def per_class_fixture():
    return SomeObject()

@pytest.fixture(scope="module")  # Shared within module
def per_module_fixture():
    return SomeObject()

@pytest.fixture(scope="session")  # Shared across all tests
def per_session_fixture():
    return SomeObject()
```

---

## Testing Patterns

### Testing Return Values

```python
def test_message_user_creates_user_message(self):
    """Message.user() should create a user message."""
    msg = Message.user("Hello!")

    assert msg.role == "user"
    assert msg.content == "Hello!"
```

### Testing Exceptions

```python
def test_registry_get_unknown_raises_keyerror(self):
    """ToolRegistry.get() should raise KeyError for unknown tools."""
    registry = ToolRegistry()

    with pytest.raises(KeyError) as exc_info:
        registry.get("nonexistent")

    assert "nonexistent" in str(exc_info.value)
```

### Testing Side Effects

```python
def test_session_add_event_appends_to_list(self):
    """Session.add_event() should append to events list."""
    session = Session()
    event = Event(event_type=EventType.CALL_START)

    session.add_event(event)

    assert len(session.events) == 1
    assert session.events[0] is event
```

### Testing with Mocks

```python
def test_agent_calls_adapter(self, mock_adapter, sample_messages):
    """Agent.call() should invoke the adapter."""
    agent = Agent(mock_adapter)

    # This will raise NotImplementedError in placeholder
    # Once implemented:
    # result = agent.call(sample_messages)
    # assert len(mock_adapter.calls) == 1
    # assert mock_adapter.calls[0]["messages"] == sample_messages
    pass
```

---

## Parameterized Tests

Test multiple inputs with one test:

```python
@pytest.mark.parametrize("role", ["system", "user", "assistant", "tool"])
def test_message_accepts_valid_roles(self, role):
    """Message should accept all valid roles."""
    msg = Message(role=role, content="test")
    assert msg.role == role

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase_variations(self, input, expected):
    """Test uppercase with various inputs."""
    assert input.upper() == expected
```

### Complex Parameters

```python
@pytest.mark.parametrize("messages,expected_count", [
    ([], 0),
    ([{"role": "user", "content": "hi"}], 1),
    ([{"role": "system", "content": "..."}, {"role": "user", "content": "hi"}], 2),
])
def test_message_list_length(self, messages, expected_count):
    """Test with various message lists."""
    assert len(messages) == expected_count
```

---

## Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_complete(self):
    """Test async completion method."""
    adapter = MockAsyncAdapter()

    result = await adapter.complete_async(messages)

    assert result.content == "response"
```

Requires `pytest-asyncio`:
```bash
pip install pytest-asyncio
```

---

## Testing Private Methods

**Don't test private methods directly.** Test through the public API.

```python
# Don't do this:
def test_internal_helper(self):
    agent = Agent(adapter)
    result = agent._internal_helper()  # Testing private method

# Do this instead:
def test_public_method_uses_helper_correctly(self):
    agent = Agent(adapter)
    result = agent.call(messages)  # Test through public API
    # Assert the overall behavior is correct
```

---

## Test Organization Tips

### Group Related Tests

```python
class TestMessageCreation:
    """Tests for creating Message objects."""

    def test_create_with_role_and_content(self): ...
    def test_create_with_optional_name(self): ...
    def test_create_with_metadata(self): ...


class TestMessageSerialization:
    """Tests for Message serialization."""

    def test_to_dict_basic(self): ...
    def test_to_dict_with_all_fields(self): ...
    def test_from_dict_basic(self): ...
```

### Use Descriptive Docstrings

```python
def test_session_save_creates_json_file(self, tmp_path):
    """
    Session.save() should create a JSON file at the specified path
    containing all session data including events and metadata.
    """
    pass
```

---

## Integration Tests

### Setup

```python
# tests/integration/test_openai_adapter.py

import os
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled",
    ),
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    ),
]
```

### Writing Integration Tests

```python
class TestOpenAIAdapterIntegration:
    """Integration tests for OpenAI adapter."""

    def test_simple_completion(self):
        """Should successfully complete a simple message."""
        adapter = OpenAIAdapter()
        messages = [{"role": "user", "content": "Say 'test' and nothing else."}]

        response = adapter.complete(messages)

        assert "test" in response.content.lower()
        assert response.usage is not None

    def test_with_system_prompt(self):
        """Should respect system prompts."""
        adapter = OpenAIAdapter()
        messages = [
            {"role": "system", "content": "Always respond in uppercase."},
            {"role": "user", "content": "hello"},
        ]

        response = adapter.complete(messages)

        assert response.content.isupper()
```

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
assert isinstance(result, Message)

# Length
assert len(items) == 3

# Approximate equality (floats)
assert result == pytest.approx(3.14, rel=0.01)

# None
assert result is None
assert result is not None

# Exception
with pytest.raises(ValueError):
    do_something()
```

---

## Running Your Tests

```bash
# Run specific test file
pytest tests/unit/test_agent.py -v

# Run specific test
pytest tests/unit/test_agent.py::TestAgent::test_agent_requires_adapter -v

# Run with print output
pytest tests/unit/test_agent.py -v -s

# Run and stop on first failure
pytest tests/unit/test_agent.py -v -x
```

---

## Test Coverage

```bash
# See uncovered lines
pytest tests/unit/ --cov=src/thoughtflow --cov-report=term-missing

# Aim for >80% coverage on new code
```

---

## Checklist for New Tests

- [ ] Test is in correct directory (unit vs integration)
- [ ] Test file named `test_<module>.py`
- [ ] Test has descriptive name and docstring
- [ ] Test follows Arrange-Act-Assert pattern
- [ ] Test is independent (no shared state)
- [ ] Test is deterministic (same result every time)
- [ ] Test runs quickly (< 1 second for unit tests)
- [ ] Test uses fixtures for common setup

---

## Next Steps

- [06-running-tests.md](06-running-tests.md) - Run your tests
- [13-adding-features.md](13-adding-features.md) - Add features with tests

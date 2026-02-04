# Running Tests

This guide explains how to run and work with the ThoughtFlow test suite.

---

## Quick Start

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run a specific test file
pytest tests/unit/test_agent.py -v

# Run a specific test class
pytest tests/unit/test_agent.py::TestAgent -v

# Run a specific test
pytest tests/unit/test_agent.py::TestAgent::test_agent_requires_adapter -v
```

---

## Test Organization

```
tests/
├── conftest.py         # Shared fixtures
├── unit/               # Fast, deterministic tests
│   ├── test_agent.py
│   ├── test_message.py
│   └── test_trace.py
└── integration/        # Tests requiring external services
    ├── test_openai_adapter.py
    └── test_anthropic_adapter.py
```

### Unit Tests vs Integration Tests

| Type | Speed | External Services | When to Run |
|------|-------|-------------------|-------------|
| Unit | Fast (<1s each) | None | Every commit |
| Integration | Slow (seconds) | API keys required | Before PR, CI |

---

## Running Unit Tests

### Basic Commands

```bash
# All unit tests
pytest tests/unit/

# With verbose output
pytest tests/unit/ -v

# With very verbose output (see print statements)
pytest tests/unit/ -vv

# Stop on first failure
pytest tests/unit/ -x

# Run last failed tests first
pytest tests/unit/ --lf
```

### Filtering Tests

```bash
# Run tests matching a keyword
pytest tests/unit/ -k "agent"
pytest tests/unit/ -k "test_message and not serialize"

# Run tests in a specific file
pytest tests/unit/test_message.py

# Run a specific test class
pytest tests/unit/test_message.py::TestMessage

# Run a specific test method
pytest tests/unit/test_message.py::TestMessage::test_create_message
```

---

## Running Integration Tests

Integration tests require:
1. API keys set as environment variables
2. `THOUGHTFLOW_INTEGRATION_TESTS=1` environment variable

```bash
# Set up environment
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export THOUGHTFLOW_INTEGRATION_TESTS=1

# Run integration tests
pytest tests/integration/ -v

# Run only OpenAI tests
pytest tests/integration/test_openai_adapter.py -v

# Run only Anthropic tests
pytest tests/integration/test_anthropic_adapter.py -v
```

### One-liner (Temporary Environment)

```bash
THOUGHTFLOW_INTEGRATION_TESTS=1 OPENAI_API_KEY=sk-... pytest tests/integration/test_openai_adapter.py -v
```

---

## Test Coverage

### Generate Coverage Report

```bash
# Run with coverage
pytest tests/unit/ --cov=src/thoughtflow

# With line numbers of missing coverage
pytest tests/unit/ --cov=src/thoughtflow --cov-report=term-missing

# Generate HTML report
pytest tests/unit/ --cov=src/thoughtflow --cov-report=html

# Open report (macOS)
open htmlcov/index.html
```

### Coverage Configuration

Coverage settings are in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/thoughtflow"]
branch = true
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

---

## Using Fixtures

Fixtures are defined in `tests/conftest.py`:

```python
# Available fixtures:

@pytest.fixture
def sample_messages():
    """Sample message list for testing."""
    return [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"},
    ]

@pytest.fixture
def mock_adapter():
    """Mock adapter that returns canned responses."""
    return MockAdapter()
```

### Using Fixtures in Tests

```python
def test_agent_with_messages(mock_adapter, sample_messages):
    """Test that uses fixtures."""
    agent = Agent(mock_adapter)
    # Use sample_messages and mock_adapter...
```

---

## Debugging Tests

### Print Output

```bash
# Show print statements
pytest tests/unit/test_agent.py -v -s

# Or equivalently
pytest tests/unit/test_agent.py -v --capture=no
```

### Drop into Debugger

```python
# Add this in your test
def test_something():
    x = compute_something()
    breakpoint()  # Drops into pdb
    assert x == expected
```

```bash
# Run the test
pytest tests/unit/test_agent.py::test_something -v -s
```

### Using pdb Commands

Once in the debugger:
```
(Pdb) p x          # Print variable
(Pdb) pp x         # Pretty print
(Pdb) l            # List code around current line
(Pdb) n            # Next line
(Pdb) s            # Step into function
(Pdb) c            # Continue to next breakpoint
(Pdb) q            # Quit debugger
```

---

## Test Markers

### Skip Tests

```python
import pytest

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_unix_specific():
    pass
```

### Expected Failures

```python
@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug():
    pass
```

### Custom Markers

```python
@pytest.mark.integration
def test_openai_real_call():
    """Requires API key."""
    pass

@pytest.mark.slow
def test_performance():
    """Takes a long time."""
    pass
```

### Running Marked Tests

```bash
# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Combine markers
pytest -m "integration and not slow"
```

---

## Parameterized Tests

Test multiple inputs with a single test:

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("123", "123"),
    ("", ""),
])
def test_uppercase(input, expected):
    from thoughtflow.message import Message
    # Test with each input/expected pair
    assert input.upper() == expected
```

---

## Testing Exceptions

```python
import pytest

def test_raises_not_implemented():
    agent = Agent(mock_adapter)

    with pytest.raises(NotImplementedError) as exc_info:
        agent.call([])

    assert "placeholder" in str(exc_info.value).lower()

def test_raises_value_error():
    with pytest.raises(ValueError, match="must be positive"):
        do_something(-1)
```

---

## Running Tests in CI

The CI pipeline runs these commands:

```bash
# Lint
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Type check
mypy src/

# Unit tests with coverage
pytest tests/unit/ -v --cov=src/thoughtflow
```

To replicate CI locally:

```bash
# Run all checks
pre-commit run --all-files

# Then run tests
pytest tests/unit/ -v
```

---

## Test Best Practices

### Do

- ✅ One assertion per test (when possible)
- ✅ Test names describe what's being tested
- ✅ Use fixtures for common setup
- ✅ Keep tests independent (no shared state)
- ✅ Test edge cases and error conditions

### Don't

- ❌ Test private methods directly
- ❌ Test exact LLM output (non-deterministic)
- ❌ Rely on test execution order
- ❌ Use `time.sleep()` in unit tests
- ❌ Access external services in unit tests

---

## Common Issues

### "Module not found"

```bash
# Make sure ThoughtFlow is installed
pip install -e ".[dev]"
```

### Tests pass locally but fail in CI

```bash
# Check Python version matches CI
python --version

# Run with same Python version as CI
pyenv install 3.11
pyenv local 3.11
pip install -e ".[dev]"
pytest tests/unit/ -v
```

### Fixture not found

Make sure `conftest.py` is in the `tests/` directory and the fixture is defined there.

---

## Next Steps

- [07-linting-formatting.md](07-linting-formatting.md) - Fix code style issues
- [12-writing-tests.md](12-writing-tests.md) - Write your own tests

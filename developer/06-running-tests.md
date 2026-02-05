# Running Tests

This guide explains how to run and work with the ThoughtFlow test suite.

**Important**: All test operations use only Python standard library tools. The only external dependency is `pytest` itself (a dev dependency). No additional test tools require external imports.

---

## Quick Start

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run a specific test file
pytest tests/unit/test_memory.py -v

# Run a specific test class
pytest tests/unit/test_memory.py::TestMemoryInitialization -v

# Run a specific test
pytest tests/unit/test_memory.py::TestMemoryInitialization::test_creates_unique_id -v
```

---

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures (MEMORY, MockLLM, etc.)
├── unit/                    # Fast, deterministic tests
│   ├── test_util.py         # EventStamp, valid_extract, compression
│   ├── test_llm.py          # LLM class (mocked HTTP)
│   ├── test_memory.py       # MEMORY class
│   ├── test_thought.py      # THOUGHT class
│   ├── test_action.py       # ACTION class
│   ├── test_message.py      # Message utilities
│   └── test_trace.py        # Tracing utilities
└── integration/             # Tests requiring external services
    └── test_llm_providers.py  # Real API tests (OpenAI, Anthropic, etc.)
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

### Testing Specific Components

```bash
# Test MEMORY class
pytest tests/unit/test_memory.py -v

# Test THOUGHT class
pytest tests/unit/test_thought.py -v

# Test ACTION class
pytest tests/unit/test_action.py -v

# Test utilities (EventStamp, valid_extract, compression)
pytest tests/unit/test_util.py -v

# Test LLM class (with mocked HTTP)
pytest tests/unit/test_llm.py -v
```

### Filtering Tests

```bash
# Run tests matching a keyword
pytest tests/unit/ -k "memory"
pytest tests/unit/ -k "test_message and not serialize"

# Run tests by marker
pytest tests/unit/ -m "not slow"
```

---

## Running Integration Tests

Integration tests make **real HTTP calls** to LLM providers. They are skipped by default to avoid:
- Unexpected API costs
- Failures due to missing API keys
- Network-dependent test results

### Enable Integration Tests

Set the required environment variables:

```bash
# Required to enable integration tests
export THOUGHTFLOW_INTEGRATION_TESTS=1

# API keys (set the ones you have)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export GOOGLE_API_KEY="..."
export OPENROUTER_API_KEY="sk-or-..."

# Run integration tests
pytest tests/integration/ -v
```

### Run Specific Provider Tests

```bash
# OpenAI only
THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_llm_providers.py::TestOpenAIIntegration -v

# Anthropic only
THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_llm_providers.py::TestAnthropicIntegration -v

# End-to-end workflows
THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_llm_providers.py::TestEndToEndWorkflows -v
```

### One-liner (Temporary Environment)

```bash
THOUGHTFLOW_INTEGRATION_TESTS=1 OPENAI_API_KEY=sk-... pytest tests/integration/test_llm_providers.py::TestOpenAIIntegration -v
```

---

## Understanding Test Output

### Successful Test Run

```
tests/unit/test_memory.py::TestMemoryInitialization::test_creates_unique_id PASSED
tests/unit/test_memory.py::TestMemoryInitialization::test_starts_with_empty_state PASSED
tests/unit/test_memory.py::TestMessageOperations::test_add_msg_stores_message PASSED
...
==================== 45 passed in 0.52s ====================
```

### Failed Test Output

```
FAILED tests/unit/test_memory.py::TestMessageOperations::test_add_msg_stores_message
============== FAILURES ==============
___ TestMessageOperations.test_add_msg_stores_message ___

    def test_add_msg_stores_message(self, memory):
        """
        add_msg must store a message that can be retrieved.
        ...
        """
        memory.add_msg('user', 'Hello!', channel='webapp')
        msgs = memory.get_msgs()

>       assert len(msgs) == 1
E       AssertionError: assert 0 == 1

tests/unit/test_memory.py:85: AssertionError
```

### Skipped Tests

```
tests/integration/test_llm_providers.py::TestOpenAIIntegration::test_basic_completion SKIPPED
  Reason: OPENAI_API_KEY not set
```

---

## Test Coverage

### Generate Coverage Report

```bash
# Run with coverage (terminal output)
pytest tests/unit/ --cov=src/thoughtflow

# With line numbers of missing coverage
pytest tests/unit/ --cov=src/thoughtflow --cov-report=term-missing

# Generate HTML report
pytest tests/unit/ --cov=src/thoughtflow --cov-report=html

# Open report (macOS)
open htmlcov/index.html
```

### Coverage by Module

```bash
# See coverage for specific modules
pytest tests/unit/test_memory.py --cov=src/thoughtflow/memory --cov-report=term-missing
pytest tests/unit/test_thought.py --cov=src/thoughtflow/thought --cov-report=term-missing
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

Fixtures are defined in `tests/conftest.py`. All fixtures use only Python standard library.

### Core Fixtures

```python
# Fresh MEMORY instance
@pytest.fixture
def memory():
    from thoughtflow import MEMORY
    return MEMORY()

# MEMORY with pre-populated state
@pytest.fixture
def populated_memory(memory):
    memory.add_msg('system', 'You are helpful.', channel='test')
    memory.add_msg('user', 'Hello!', channel='test')
    memory.set_var('user_name', 'Alice')
    return memory

# MockLLM class for testing without HTTP
@pytest.fixture
def mock_llm():
    return MockLLM  # Returns the class, not instance

# Pre-instantiated MockLLM
@pytest.fixture
def mock_llm_instance():
    return MockLLM()
```

### Using Fixtures in Tests

```python
def test_memory_stores_messages(memory):
    """Test using the memory fixture."""
    memory.add_msg('user', 'Hello!', channel='webapp')
    assert len(memory.get_msgs()) == 1

def test_thought_with_mock_llm(mock_llm, memory):
    """Test using both mock_llm and memory fixtures."""
    llm = mock_llm(responses=["Hello!"])
    thought = THOUGHT(name="test", llm=llm, prompt="Hi")
    thought(memory)
    assert llm.call_count == 1
```

---

## Debugging Tests

### Print Output

```bash
# Show print statements
pytest tests/unit/test_memory.py -v -s

# Or equivalently
pytest tests/unit/test_memory.py -v --capture=no
```

### Drop into Debugger

```python
# Add this in your test
def test_something(memory):
    memory.set_var('x', 1)
    breakpoint()  # Drops into pdb
    assert memory.get_var('x') == 1
```

```bash
# Run the test
pytest tests/unit/test_memory.py::test_something -v -s
```

### Using pdb Commands

Once in the debugger:
```
(Pdb) p memory.get_var('x')  # Print variable
(Pdb) pp memory.events       # Pretty print
(Pdb) l                      # List code around current line
(Pdb) n                      # Next line
(Pdb) s                      # Step into function
(Pdb) c                      # Continue to next breakpoint
(Pdb) q                      # Quit debugger
```

---

## Test Markers

### Built-in Markers

```python
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_unix_specific():
    pass

@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug():
    pass
```

### Custom Markers (defined in conftest.py)

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
@pytest.mark.parametrize("role", ["user", "assistant", "system"])
def test_memory_accepts_valid_roles(self, memory, role):
    """MEMORY should accept all valid roles."""
    memory.add_msg(role, "content", channel="webapp")
    assert memory.get_msgs()[0]['role'] == role

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
])
def test_uppercase(self, input, expected):
    assert input.upper() == expected
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
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/

# Then run tests
pytest tests/unit/ -v --cov=src/thoughtflow
```

---

## Analyzing Test Results

### Summary Statistics

```bash
# Quick summary
pytest tests/unit/ -v --tb=no

# Count tests by result
pytest tests/unit/ -v --tb=no | grep -E "passed|failed|skipped"
```

### Identifying Slow Tests

```bash
# Show slowest 10 tests
pytest tests/unit/ --durations=10
```

### Test Report (JSON format)

```bash
# Generate JSON report
pytest tests/unit/ --json-report --json-report-file=report.json

# Or use built-in JUnit XML (works with many CI systems)
pytest tests/unit/ --junitxml=report.xml
```

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

### Mock LLM not working

```python
# Use the fixture correctly - it returns a CLASS
def test_with_mock(mock_llm, memory):
    llm = mock_llm(responses=["Expected response"])  # Instantiate it
    # Not: llm = mock_llm  # This is wrong
```

---

## Next Steps

- [07-linting-formatting.md](07-linting-formatting.md) - Fix code style issues
- [12-writing-tests.md](12-writing-tests.md) - Write your own tests

# Fixing Bugs

This guide walks through the process of finding and fixing bugs in ThoughtFlow.

---

## Bug Fixing Workflow

### 1. Understand the Bug

Before fixing, understand:
- What is the expected behavior?
- What is the actual behavior?
- Can you reproduce it consistently?

### 2. Create a Reproduction

```python
# Create a minimal script that reproduces the bug
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

adapter = OpenAIAdapter()
agent = Agent(adapter)

# This causes the bug:
result = agent.call([])  # Unexpected behavior here
```

### 3. Write a Failing Test

```python
# tests/unit/test_agent.py

def test_agent_call_with_empty_messages_raises_error(self):
    """Bug #123: Agent.call() should raise error for empty messages."""
    agent = Agent(mock_adapter)

    with pytest.raises(ValueError, match="messages cannot be empty"):
        agent.call([])
```

Run the test to confirm it fails:
```bash
pytest tests/unit/test_agent.py::TestAgent::test_agent_call_with_empty_messages_raises_error -v
# Expected: FAILED
```

### 4. Create a Branch

```bash
git checkout -b fix/empty-messages-error
```

### 5. Fix the Bug

```python
# src/thoughtflow/agent.py

def call(
    self,
    msg_list: MessageList,
    params: dict[str, Any] | None = None,
) -> str:
    """Call the agent with messages."""
    # Add validation
    if not msg_list:
        raise ValueError("messages cannot be empty")

    # ... rest of implementation
```

### 6. Verify the Fix

```bash
# Run the specific test
pytest tests/unit/test_agent.py::TestAgent::test_agent_call_with_empty_messages_raises_error -v
# Expected: PASSED

# Run all tests to ensure no regressions
pytest tests/unit/ -v
```

### 7. Update CHANGELOG

```markdown
## [Unreleased]

### Fixed
- `Agent.call()` now raises `ValueError` for empty message lists (#123)
```

### 8. Create Pull Request

Reference the issue in your PR:
```markdown
## Description

Fixes the bug where `Agent.call()` would silently fail with empty messages.

## Related Issue

Fixes #123
```

---

## Common Bug Patterns

### 1. None/Null Handling

**Bug:** Code assumes value is not None

```python
# Before (buggy)
def process(self, data: dict | None) -> str:
    return data["key"]  # Crashes if data is None!

# After (fixed)
def process(self, data: dict | None) -> str:
    if data is None:
        return ""
    return data.get("key", "")
```

### 2. Type Errors

**Bug:** Wrong type passed or returned

```python
# Before (buggy)
def get_count(self) -> int:
    return str(self.count)  # Returns string, not int!

# After (fixed)
def get_count(self) -> int:
    return int(self.count)
```

### 3. Missing Error Handling

**Bug:** Exception not caught

```python
# Before (buggy)
def load_config(self, path: str) -> dict:
    with open(path) as f:
        return json.load(f)  # Crashes if file doesn't exist!

# After (fixed)
def load_config(self, path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}") from e
```

### 4. Race Conditions

**Bug:** Concurrent access issues

```python
# Before (buggy)
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Not thread-safe!

# After (fixed)
import threading

class Counter:
    def __init__(self):
        self.count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self.count += 1
```

### 5. Off-by-One Errors

**Bug:** Index or count is wrong by one

```python
# Before (buggy)
def get_last_n(self, items: list, n: int) -> list:
    return items[-n + 1:]  # Wrong!

# After (fixed)
def get_last_n(self, items: list, n: int) -> list:
    return items[-n:] if n > 0 else []
```

---

## Debugging Techniques

### 1. Print Debugging

```python
def process(self, data):
    print(f"DEBUG: data = {data}")  # Temporary
    print(f"DEBUG: type = {type(data)}")  # Temporary
    result = self._internal_process(data)
    print(f"DEBUG: result = {result}")  # Temporary
    return result
```

Run with pytest `-s` flag:
```bash
pytest tests/unit/test_module.py -v -s
```

**Remember to remove print statements before committing!**

### 2. Using breakpoint()

```python
def process(self, data):
    breakpoint()  # Drops into debugger
    return self._internal_process(data)
```

```bash
pytest tests/unit/test_module.py -v -s
# Drops into pdb when breakpoint is hit
```

### 3. Logging

```python
import logging

logger = logging.getLogger(__name__)

def process(self, data):
    logger.debug(f"Processing data: {data}")
    try:
        result = self._internal_process(data)
        logger.debug(f"Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing: {e}")
        raise
```

### 4. Assertions for Invariants

```python
def process(self, items: list) -> list:
    assert len(items) > 0, "items must not be empty"  # Dev-time check

    result = [self._transform(item) for item in items]

    assert len(result) == len(items), "result length mismatch"  # Invariant
    return result
```

---

## Investigating Bug Reports

### Step 1: Gather Information

From the bug report, collect:
- Steps to reproduce
- Expected vs actual behavior
- Environment (Python version, OS, ThoughtFlow version)
- Error messages/stack traces

### Step 2: Reproduce Locally

```bash
# Create isolated environment
python -m venv .test-env
source .test-env/bin/activate
pip install thoughtflow  # Same version as reporter

# Try to reproduce
python reproduce_bug.py
```

### Step 3: Bisect if Needed

If the bug is a regression:

```bash
# Find the commit that introduced the bug
git bisect start
git bisect bad HEAD  # Current version is bad
git bisect good v0.1.0  # This version was good

# Git will checkout commits for you to test
# Mark each as good or bad:
git bisect good  # or
git bisect bad

# Eventually git finds the culprit commit
```

### Step 4: Ask for Clarification

If you can't reproduce:
```markdown
Thanks for the report! I'm having trouble reproducing this.
Could you provide:
1. The exact Python version (`python --version`)
2. The exact ThoughtFlow version (`pip show thoughtflow`)
3. A minimal code example that triggers the bug
```

---

## Bug Fix Checklist

Before submitting:

- [ ] Bug is reproducible
- [ ] Failing test written
- [ ] Bug is fixed
- [ ] Test now passes
- [ ] No regressions (all tests pass)
- [ ] CHANGELOG updated
- [ ] PR references the issue

---

## Next Steps

- [17-debugging-tips.md](17-debugging-tips.md) - More debugging techniques
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your fix

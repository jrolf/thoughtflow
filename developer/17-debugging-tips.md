# Debugging Tips

Techniques for debugging ThoughtFlow code.

---

## Quick Debugging

### Print Statements

```python
def process(self, data):
    print(f"DEBUG: data={data}, type={type(data)}")
    result = self._internal(data)
    print(f"DEBUG: result={result}")
    return result
```

Run tests with `-s`:
```bash
pytest tests/unit/test_module.py -v -s
```

### breakpoint()

```python
def process(self, data):
    breakpoint()  # Drops into pdb
    return self._internal(data)
```

### pdb Commands

| Command | Action |
|---------|--------|
| `n` | Next line |
| `s` | Step into |
| `c` | Continue |
| `p x` | Print x |
| `l` | List code |
| `q` | Quit |

---

## Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def process(self, data):
    logger.debug(f"Processing: {data}")
    try:
        result = self._internal(data)
        logger.debug(f"Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
```

---

## Tracing with Sessions

```python
from thoughtflow.trace import Session

session = Session()
response = agent.call(messages, session=session)

# Inspect what happened
for event in session.events:
    print(f"{event.event_type}: {event.data}")
```

---

## VS Code Debugging

1. Set breakpoints by clicking line numbers
2. Press F5 or use "Run and Debug"
3. Use Debug Console for evaluation

### launch.json

```json
{
    "configurations": [
        {
            "name": "Debug Test",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/unit/test_agent.py", "-v", "-s"]
        }
    ]
}
```

---

## Common Issues

### Import Errors

```bash
# Check package is installed
pip show thoughtflow

# Reinstall
pip install -e ".[dev]"
```

### Type Errors

```bash
# Run mypy for hints
mypy src/thoughtflow/module.py
```

### Test Isolation

```python
# Tests should not share state
# Use fixtures for fresh instances
@pytest.fixture
def fresh_session():
    return Session()  # New instance each test
```

---

## Getting Help

1. Check existing issues on GitHub
2. Search error messages
3. Ask in discussions with:
   - Code sample
   - Error message
   - Python/ThoughtFlow versions

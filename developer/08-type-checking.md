# Type Checking

This guide explains how to run mypy and fix type errors in ThoughtFlow.

---

## Overview

ThoughtFlow uses [mypy](https://mypy.readthedocs.io/) for static type checking. All public APIs must have type hints.

---

## Quick Commands

```bash
# Check all source code
mypy src/

# Check specific file
mypy src/thoughtflow/agent.py

# Check with more details
mypy src/ --show-error-codes

# Check and show which lines are untyped
mypy src/ --any-exprs-report .
```

---

## Running Type Checks

### Basic Check

```bash
mypy src/
```

### Understanding Output

```
src/thoughtflow/agent.py:45: error: Argument 1 to "call" has incompatible type "str"; expected "list[dict[str, Any]]"  [arg-type]
Found 1 error in 1 file (checked 15 source files)
```

Components:
- **File:Line** - Where the error is
- **error** - Severity (error, warning, note)
- **Message** - What's wrong
- **[error-code]** - Error type (useful for ignoring)

---

## Common Type Errors

### 1. Missing Return Type

```python
# Error: Function is missing a return type annotation
def get_name():
    return "ThoughtFlow"

# Fix: Add return type
def get_name() -> str:
    return "ThoughtFlow"
```

### 2. Missing Parameter Types

```python
# Error: Function is missing type annotation for parameter
def greet(name):
    return f"Hello, {name}"

# Fix: Add parameter type
def greet(name: str) -> str:
    return f"Hello, {name}"
```

### 3. Incompatible Types

```python
# Error: Incompatible types in assignment
x: int = "hello"  # Can't assign str to int

# Fix: Use correct type
x: str = "hello"
# Or fix the annotation
x: int = 42
```

### 4. Optional Values

```python
# Error: Item "None" has no attribute "upper"
def process(value: str | None) -> str:
    return value.upper()  # value might be None!

# Fix: Handle None case
def process(value: str | None) -> str:
    if value is None:
        return ""
    return value.upper()
```

### 5. Dict/List Types

```python
# Error: Need type parameters for dict
def process(data: dict):  # Too vague
    pass

# Fix: Specify key and value types
def process(data: dict[str, Any]) -> None:
    pass
```

### 6. Return Type Mismatch

```python
# Error: Returning None but declared str
def get_name() -> str:
    if condition:
        return "name"
    # Implicitly returns None!

# Fix: Ensure all paths return correct type
def get_name() -> str:
    if condition:
        return "name"
    return "default"

# Or update return type
def get_name() -> str | None:
    if condition:
        return "name"
    return None
```

---

## Type Annotations Cheat Sheet

### Basic Types

```python
x: int = 42
y: float = 3.14
z: str = "hello"
flag: bool = True
nothing: None = None
```

### Collections

```python
from typing import Any

# Lists
items: list[int] = [1, 2, 3]
mixed: list[Any] = [1, "two", 3.0]

# Dicts
data: dict[str, int] = {"a": 1, "b": 2}
config: dict[str, Any] = {"name": "test", "count": 42}

# Sets
unique: set[str] = {"a", "b", "c"}

# Tuples
pair: tuple[int, str] = (1, "one")
triple: tuple[int, ...] = (1, 2, 3)  # Variable length
```

### Optional and Union

```python
# Optional (can be None)
maybe_name: str | None = None

# Union (can be multiple types)
value: int | str = 42
value = "forty-two"  # Also valid
```

### Callable

```python
from typing import Callable

# Function that takes (int, str) and returns bool
validator: Callable[[int, str], bool]

# Function with no args returning None
callback: Callable[[], None]
```

### TypeVar (Generics)

```python
from typing import TypeVar

T = TypeVar("T")

def first(items: list[T]) -> T:
    return items[0]
```

### Protocol (Structural Typing)

```python
from typing import Protocol

class Callable(Protocol):
    def call(self, msg: str) -> str:
        ...
```

---

## Type Aliases

Create aliases for complex types:

```python
from typing import Any, TypeAlias

# Type alias
MessageDict: TypeAlias = dict[str, Any]
MessageList: TypeAlias = list[MessageDict]

# Use in annotations
def process(messages: MessageList) -> str:
    pass
```

---

## TYPE_CHECKING Block

Import types only for type checking (not at runtime):

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thoughtflow.adapters.base import Adapter

class Agent:
    def __init__(self, adapter: Adapter) -> None:
        self.adapter = adapter
```

This avoids circular imports and runtime import overhead.

---

## Ignoring Type Errors

### Ignore Specific Line

```python
x = some_dynamic_thing()  # type: ignore[assignment]
```

### Ignore All Errors on Line

```python
x = some_dynamic_thing()  # type: ignore
```

### Ignore in Function

```python
def legacy_function() -> Any:
    # mypy: ignore-errors
    ...
```

### Configure in pyproject.toml

```toml
[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
```

---

## Mypy Configuration

Configuration in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
check_untyped_defs = true
files = ["src/thoughtflow"]

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
```

### Strict Mode

`strict = true` enables:
- `disallow_untyped_defs` - All functions must have types
- `disallow_incomplete_defs` - Partial types not allowed
- `check_untyped_defs` - Check inside untyped functions
- `no_implicit_optional` - No implicit `None` in Optional

---

## Typing Third-Party Libraries

### Install Type Stubs

```bash
# Many packages have stubs on PyPI
pip install types-requests
pip install types-PyYAML
```

### Ignore Missing Imports

```python
import some_untyped_lib  # type: ignore[import]
```

Or in pyproject.toml:

```toml
[[tool.mypy.overrides]]
module = ["some_untyped_lib"]
ignore_missing_imports = true
```

---

## Gradual Typing Strategy

For existing untyped code:

### 1. Start with Public API

Add types to public functions first:

```python
def call(
    self,
    msg_list: MessageList,
    params: dict[str, Any] | None = None,
) -> str:
    ...
```

### 2. Add Internal Types Gradually

```python
def _internal_helper(data):  # Can be untyped initially
    pass
```

### 3. Use `Any` as Escape Hatch

```python
def process(data: Any) -> Any:
    # Will type properly later
    ...
```

---

## Common Fixes

### Dict with Unknown Keys

```python
# Error: TypedDict doesn't accept arbitrary keys
# Use regular dict instead
config: dict[str, Any] = {"key": "value"}
```

### Callable with Self

```python
from typing import Self

class Builder:
    def with_name(self, name: str) -> Self:
        self.name = name
        return self  # Returns same type as class
```

### Overloaded Functions

```python
from typing import overload

@overload
def process(data: str) -> str: ...
@overload
def process(data: int) -> int: ...

def process(data: str | int) -> str | int:
    if isinstance(data, str):
        return data.upper()
    return data * 2
```

---

## IDE Integration

### VS Code (Pylance)

Pylance provides real-time type checking. Enable in settings:

```json
{
    "python.analysis.typeCheckingMode": "basic"
}
```

Modes:
- `off` - No type checking
- `basic` - Common errors
- `strict` - All mypy-style checks

### PyCharm

Built-in type checking. Enable under:
**Settings** → **Editor** → **Inspections** → **Python** → **Type checker**

---

## Checking Before PR

```bash
# Full type check
mypy src/

# Should show: Success: no issues found
```

---

## Troubleshooting

### "Cannot find implementation or library stub"

```bash
pip install types-<package>
# or ignore
```

### "Incompatible types" with inheritance

Check that child class types are compatible with parent:

```python
class Parent:
    def method(self) -> int: ...

class Child(Parent):
    def method(self) -> int:  # Must match parent
        return 42
```

### Circular imports

Use `TYPE_CHECKING` block and string annotations:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .other import OtherClass

def func(obj: OtherClass) -> None:
    pass
```

---

## Next Steps

- [06-running-tests.md](06-running-tests.md) - Verify your code works
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your changes

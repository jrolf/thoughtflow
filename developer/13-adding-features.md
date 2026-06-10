# Adding Features

This guide walks through the process of adding a new feature to ThoughtFlow.

---

## Before You Start

### Check ThoughtFlow Principles

Before adding a feature, ask:

1. **Is this a primitive or a convenience?**
   - Primitives belong in core
   - Convenience wrappers belong in userland

2. **Does it increase API surface area?**
   - Every new export adds cognitive load
   - Can it extend existing primitives instead?

3. **Is the behavior explicit?**
   - No hidden state or side effects
   - Everything should be traceable

4. **Does it work across providers?**
   - Provider-specific logic belongs in the `_call_<service>` methods of llm.py/embed.py
   - Core should be provider-agnostic

---

## Feature Development Workflow

### 1. Create an Issue (Optional but Recommended)

For significant features:
1. Open a GitHub issue
2. Describe the feature and use case
3. Discuss design with maintainers
4. Get approval before starting

### 2. Create a Branch

```bash
git checkout main
git fetch upstream
git merge upstream/main
git checkout -b feature/my-new-feature
```

### 3. Write Tests First (TDD Recommended)

```python
# tests/unit/test_new_feature.py

class TestNewFeature:
    """Tests for the new feature."""

    def test_basic_functionality(self):
        """New feature should do X when given Y."""
        # Arrange
        feature = NewFeature()

        # Act
        result = feature.do_something()

        # Assert
        assert result == expected

    def test_edge_case(self):
        """New feature should handle edge case Z."""
        feature = NewFeature()
        result = feature.do_something(edge_case_input)
        assert result == expected_edge_case_result
```

### 4. Implement the Feature

```python
# src/thoughtflow/new_feature.py

"""
New feature module.

This module provides [description].

Example:
    >>> from thoughtflow import NewFeature
    >>> feature = NewFeature()
    >>> result = feature.do_something()
"""

from __future__ import annotations

from typing import Any


class NewFeature:
    """A new feature for ThoughtFlow.

    This class provides [functionality].

    Attributes:
        config: Configuration options.

    Example:
        >>> feature = NewFeature(config={"option": True})
        >>> feature.do_something()
        'result'
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the new feature.

        Args:
            config: Optional configuration dict.
        """
        self.config = config or {}

    def do_something(self, input_data: str = "") -> str:
        """Do something with the input.

        Args:
            input_data: The input to process.

        Returns:
            The processed result.

        Raises:
            ValueError: If input_data is invalid.
        """
        if not isinstance(input_data, str):
            raise ValueError("input_data must be a string")

        return f"processed: {input_data}"
```

### 5. Export from `__init__.py`

```python
# src/thoughtflow/__init__.py

from thoughtflow.new_feature import NewFeature

__all__ = [
    # ... existing exports ...
    "NewFeature",
]
```

### 6. Run Tests

```bash
# Run your new tests
pytest tests/unit/test_new_feature.py -v

# Run all tests to ensure nothing broke
pytest tests/unit/ -v

# Check types
mypy src/

# Check lint
ruff check src/ tests/
```

### 7. Add Documentation

```markdown
<!-- docs/concepts/new_feature.md -->

# New Feature

Description of the new feature.

## Basic Usage

```python
from thoughtflow import NewFeature

feature = NewFeature()
result = feature.do_something()
```

## Configuration

...

## Examples

...
```

Update `mkdocs.yml`:

```yaml
nav:
  - Concepts:
    - New Feature: concepts/new_feature.md
```

### 8. Add Example (if applicable)

```python
# examples/XX_new_feature.py

#!/usr/bin/env python3
"""
ThoughtFlow Example: New Feature

Demonstrates how to use the new feature.
"""

from thoughtflow import NewFeature


def main():
    feature = NewFeature()
    result = feature.do_something("hello")
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
```

### 9. Update CHANGELOG

```markdown
<!-- CHANGELOG.md -->

## [Unreleased]

### Added
- New `NewFeature` class for [purpose] (#123)
```

### 10. Create Pull Request

See [09-creating-pull-requests.md](09-creating-pull-requests.md).

---

## Example: Adding a New Provider

Providers are not separate modules — each one is a `_call_<service>` method on the `LLM` class in `src/thoughtflow/llm.py`, plus a dispatch entry in `call()`. The implementation must use only the standard library (`urllib`, `json`).

```python
# src/thoughtflow/llm.py

def _call_bedrock(self, msg_list, params):
    """Calls AWS Bedrock via its OpenAI-compatible REST endpoint."""
    output_schema = params.pop('_output_schema', None)
    payload = {
        "model": self.model,
        "messages": self._prepare_messages(msg_list),
        **params
    }
    # ... build url/headers, call self._send_request(), parse choices ...
```

Then add the dispatch branch in `LLM.call()`, a `PROVIDER_ROLE_MAP` entry if the provider needs role translation, unit tests with a monkeypatched transport, and an integration test gated by `THOUGHTFLOW_INTEGRATION_TESTS=1`.

See [15-adding-providers.md](15-adding-providers.md) for the complete step-by-step guide.

---

## Feature Checklist

Before submitting:

- [ ] Code follows project style (Ruff formatted)
- [ ] Types are complete (mypy passes)
- [ ] Tests cover main functionality
- [ ] Tests cover edge cases
- [ ] Documentation added
- [ ] Example added (if user-facing)
- [ ] CHANGELOG updated
- [ ] All existing tests still pass

---

## Next Steps

- [12-writing-tests.md](12-writing-tests.md) - Write comprehensive tests
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your feature

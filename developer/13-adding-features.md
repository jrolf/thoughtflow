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
   - Provider-specific logic belongs in adapters
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

## Example: Adding a New Adapter

### Step 1: Create the Adapter File

```python
# src/thoughtflow/adapters/bedrock.py

"""
AWS Bedrock adapter for ThoughtFlow.

Provides integration with AWS Bedrock managed LLM service.

Requires: pip install thoughtflow[bedrock]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from thoughtflow.adapters.base import Adapter, AdapterConfig, AdapterResponse

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


class BedrockAdapter(Adapter):
    """Adapter for AWS Bedrock.

    Example:
        >>> adapter = BedrockAdapter(region="us-east-1")
        >>> response = adapter.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
    """

    DEFAULT_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"

    def __init__(
        self,
        region: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Bedrock adapter.

        Args:
            region: AWS region. Defaults to AWS_DEFAULT_REGION env var.
            config: Full adapter configuration.
            **kwargs: Additional config options.
        """
        if config is None:
            config = AdapterConfig(**kwargs)
        super().__init__(config)
        self.region = region
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the Bedrock client."""
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise ImportError(
                    "boto3 not installed. "
                    "Install with: pip install thoughtflow[bedrock]"
                ) from e

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
            )
        return self._client

    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate completion using Bedrock."""
        # Implementation here
        raise NotImplementedError("BedrockAdapter.complete() not yet implemented")

    def get_capabilities(self) -> dict[str, Any]:
        """Get Bedrock adapter capabilities."""
        return {
            "streaming": True,
            "tool_calling": True,
            "vision": True,
            "json_mode": False,
        }
```

### Step 2: Add to Adapters `__init__.py`

```python
# src/thoughtflow/adapters/__init__.py

__all__ = [
    # ... existing ...
    "BedrockAdapter",
]

def __getattr__(name: str):
    # ... existing ...
    elif name == "BedrockAdapter":
        from thoughtflow.adapters.bedrock import BedrockAdapter
        return BedrockAdapter
    # ...
```

### Step 3: Add Optional Dependency

```toml
# pyproject.toml

[project.optional-dependencies]
bedrock = ["boto3>=1.28"]
all-providers = [
    # ... existing ...
    "thoughtflow[bedrock]",
]
```

### Step 4: Write Tests

```python
# tests/unit/test_bedrock_adapter.py

from thoughtflow.adapters.bedrock import BedrockAdapter


class TestBedrockAdapter:
    def test_initialization(self):
        """Should initialize with region."""
        adapter = BedrockAdapter(region="us-east-1")
        assert adapter.region == "us-east-1"

    def test_capabilities(self):
        """Should report correct capabilities."""
        adapter = BedrockAdapter()
        caps = adapter.get_capabilities()
        assert caps["tool_calling"] is True
```

### Step 5: Add Integration Test

```python
# tests/integration/test_bedrock_adapter.py

import os
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled",
    ),
]


class TestBedrockAdapterIntegration:
    def test_real_completion(self):
        """Should complete with real Bedrock API."""
        # Requires AWS credentials configured
        pass
```

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

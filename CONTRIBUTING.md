# Contributing to ThoughtFlow

Thank you for your interest in contributing to ThoughtFlow! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Release Process](#release-process)
- [ThoughtFlow Principles](#thoughtflow-principles)

---

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive environment for all contributors.

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- A GitHub account

### First-Time Contributors

1. Look for issues labeled `good first issue` or `help wanted`
2. Comment on the issue to let others know you're working on it
3. Fork the repository and create a branch
4. Make your changes and submit a pull request

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/thoughtflow.git
cd thoughtflow
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Development Dependencies

```bash
# Install in editable mode with all dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 4. Verify Setup

```bash
# Run tests
pytest tests/unit/ -v

# Run linter
ruff check src/ tests/

# Run formatter check
ruff format --check src/ tests/

# Run type checker
mypy src/
```

---

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-bedrock-adapter` - New features
- `fix/message-serialization` - Bug fixes
- `docs/update-quickstart` - Documentation
- `refactor/simplify-trace-events` - Refactoring

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

Longer description if needed.

Fixes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting (no code change)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(adapters): add Bedrock adapter for AWS

fix(trace): prevent duplicate events in session

docs(readme): add installation instructions for Windows
```

---

## Pull Request Process

### 1. Before Submitting

- [ ] All tests pass: `pytest tests/unit/ -v`
- [ ] Code is formatted: `ruff format src/ tests/`
- [ ] Linter passes: `ruff check src/ tests/`
- [ ] Type checker passes: `mypy src/`
- [ ] Documentation is updated (if applicable)
- [ ] CHANGELOG.md is updated (for features/fixes)

### 2. PR Description

Use the PR template and include:

- **What**: Clear description of changes
- **Why**: Motivation and context
- **How**: Technical approach (if complex)
- **Testing**: How you verified the changes

### 3. Review Process

1. Automated checks run (CI)
2. Maintainer reviews code
3. Address any feedback
4. Once approved, maintainer merges

### 4. After Merge

- Delete your branch
- Pull latest `main` to your fork

---

## Coding Standards

### Style Guide

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Format code
ruff format src/ tests/

# Check and fix lint issues
ruff check --fix src/ tests/
```

### Type Hints

All public APIs must have type hints:

```python
def call(
    self,
    msg_list: MessageList,
    params: dict[str, Any] | None = None,
) -> str:
    """Call the agent with messages.

    Args:
        msg_list: List of message dicts.
        params: Optional parameters.

    Returns:
        The agent's response.
    """
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def example_function(arg1: str, arg2: int = 10) -> bool:
    """Short description of function.

    Longer description if needed. Can span multiple lines
    and include examples.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When arg1 is empty.

    Example:
        >>> example_function("test", 20)
        True
    """
    ...
```

### Import Organization

Imports are automatically organized by Ruff. The order is:

1. Standard library
2. Third-party packages
3. Local imports

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from thoughtflow.agent import Agent
from thoughtflow.trace import Session
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Fast, deterministic, no external dependencies
│   ├── test_agent.py
│   ├── test_message.py
│   └── ...
└── integration/    # Requires API keys, slower
    ├── test_openai_adapter.py
    └── ...
```

### Writing Unit Tests

```python
class TestMyFeature:
    """Tests for MyFeature."""

    def test_basic_functionality(self) -> None:
        """MyFeature should do X when given Y."""
        # Arrange
        input_data = ...

        # Act
        result = my_feature(input_data)

        # Assert
        assert result == expected

    def test_edge_case(self) -> None:
        """MyFeature should handle edge case Z."""
        ...
```

### Test Naming

- Test class: `TestClassName`
- Test method: `test_what_it_does` or `test_condition_expected_result`
- Use descriptive docstrings

### Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Specific test file
pytest tests/unit/test_agent.py -v

# With coverage
pytest tests/unit/ -v --cov=src/thoughtflow --cov-report=html

# Integration tests (requires API keys)
THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/ -v
```

### What Makes a Good Test

- **Deterministic**: Same result every time
- **Isolated**: No dependencies on other tests
- **Fast**: Unit tests should run in milliseconds
- **Focused**: Test one thing per test
- **Readable**: Clear what's being tested

### What to Avoid

- Testing exact model output (non-deterministic)
- Tests that require external services (unless integration test)
- Brittle tests that break on formatting changes

---

## Documentation

### Where Documentation Lives

- `README.md` - Project overview, quick start
- `docs/` - Full documentation (MkDocs)
- Docstrings - API reference (auto-generated)
- `examples/` - Runnable code examples

### Building Docs Locally

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve locally
mkdocs serve

# Open http://127.0.0.1:8000
```

### Documentation Standards

- Use clear, concise language
- Include code examples
- Keep examples runnable
- Update docs when changing APIs

---

## Release Process

Releases are managed by maintainers. Here's how it works:

### Version Numbers

We use [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- `0.x.x` = Pre-stable (breaking changes allowed in minor)
- `x.0.0` = Major (breaking changes)
- `x.x.0` = Minor (new features, backward compatible)
- `x.x.x` = Patch (bug fixes only)

### Release Steps (Maintainers)

1. Create release branch: `git checkout -b release/0.2.0`
2. Update version in `pyproject.toml`
3. Update `CHANGELOG.md`
4. Create PR to `main`
5. After merge, tag: `git tag v0.2.0 && git push origin v0.2.0`
6. GitHub Actions publishes to PyPI automatically

---

## ThoughtFlow Principles

When contributing, please keep these principles in mind:

### 1. Tiny Surface Area

> Ask: "Is this a new primitive, or a convenience wrapper?"

- Prefer extending existing primitives over adding new ones
- Convenience wrappers belong in userland, not core
- Every addition increases cognitive load

### 2. Explicit State

> Ask: "Can a user see what happened?"

- No hidden state mutations
- All behavior should be traceable
- Sessions capture everything

### 3. Portability

> Ask: "Does this work across providers and environments?"

- Adapters handle provider differences
- Core remains provider-agnostic
- Keep dependencies minimal

### 4. Deterministic Testing

> Ask: "Can this be tested without external services?"

- Provide mocking/simulation patterns
- Support record/replay workflows
- Avoid non-determinism in core

### What Good Contributions Look Like

✅ Reduces complexity somewhere
✅ Improves determinism or replayability
✅ Adds capability without increasing surface area
✅ Strengthens adapter correctness
✅ Adds examples that teach patterns

### What Risky Contributions Look Like

⚠️ Adds new abstraction layers
⚠️ Introduces implicit behavior
⚠️ Couples tightly to a vendor
⚠️ Increases dependency weight significantly
⚠️ Makes state transitions harder to reason about

---

## Questions?

- Open a [Discussion](https://github.com/jrolf/thoughtflow/discussions) for questions
- Open an [Issue](https://github.com/jrolf/thoughtflow/issues) for bugs or feature requests
- Email maintainers: james@think.dev

Thank you for contributing to ThoughtFlow! 🎉

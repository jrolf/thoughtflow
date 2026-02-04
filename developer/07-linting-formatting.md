# Linting and Formatting

This guide explains how to format code and fix linting errors using Ruff.

---

## Overview

ThoughtFlow uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Ruff is fast and replaces multiple tools (Black, isort, Flake8, etc.).

---

## Quick Commands

```bash
# Format all code
ruff format src/ tests/

# Check for lint errors
ruff check src/ tests/

# Fix auto-fixable lint errors
ruff check --fix src/ tests/

# Check formatting without changing files
ruff format --check src/ tests/
```

---

## Formatting Code

### Format Everything

```bash
ruff format src/ tests/ examples/
```

### Format a Single File

```bash
ruff format src/thoughtflow/agent.py
```

### Check Without Changing

```bash
# Returns non-zero exit code if files would change
ruff format --check src/ tests/
```

### What Ruff Format Does

- Consistent indentation (4 spaces)
- Line length limit (88 characters)
- Consistent quote style (double quotes)
- Trailing commas in multi-line structures
- Import sorting

**Before:**

```python
from thoughtflow.trace import Session
from thoughtflow import Agent
import json
from typing import Any,Dict

def example(  x:str,y:int=10   )->Dict[str,Any]:
    return {'x':x,'y':y}
```

**After:**

```python
import json
from typing import Any, Dict

from thoughtflow import Agent
from thoughtflow.trace import Session


def example(x: str, y: int = 10) -> Dict[str, Any]:
    return {"x": x, "y": y}
```

---

## Linting Code

### Check for Errors

```bash
ruff check src/ tests/
```

### Fix Auto-fixable Errors

```bash
ruff check --fix src/ tests/
```

### Common Lint Errors

| Code | Description | Auto-fix |
|------|-------------|----------|
| `F401` | Module imported but unused | ✅ |
| `F841` | Local variable assigned but never used | ❌ |
| `E501` | Line too long | ❌ |
| `I001` | Import block not sorted | ✅ |
| `B006` | Mutable default argument | ❌ |

### Example Fixes

**F401: Unused import**
```python
# Before
import os  # F401: 'os' imported but unused
from typing import Any

# After (auto-fixed)
from typing import Any
```

**F841: Unused variable**
```python
# Before
def example():
    unused = compute()  # F841: Local variable 'unused' assigned but never used
    return 42

# After (manual fix - remove or use it)
def example():
    return 42
```

**B006: Mutable default argument**
```python
# Before (dangerous!)
def example(items: list = []):  # B006
    items.append(1)
    return items

# After (safe)
def example(items: list | None = None):
    if items is None:
        items = []
    items.append(1)
    return items
```

---

## Ignoring Lint Errors

### Ignore Specific Line

```python
import unused_module  # noqa: F401
```

### Ignore Multiple Rules

```python
x = 1  # noqa: F841, E501
```

### Ignore for Entire File

Add at the top of the file:
```python
# ruff: noqa: F401
```

### Configure in ruff.toml

For project-wide ignores, edit `ruff.toml`:

```toml
[lint]
ignore = [
    "E501",  # Line too long (handled by formatter)
]
```

### Per-file Ignores

```toml
[lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # Allow assert in tests
"__init__.py" = ["F401"]    # Allow unused imports in __init__
```

---

## Import Sorting

Ruff automatically sorts imports:

1. Standard library (`import os`, `from typing import ...`)
2. Third-party (`import pytest`, `from openai import ...`)
3. Local (`from thoughtflow import ...`)

### Configuring First-Party Imports

In `ruff.toml`:

```toml
[lint.isort]
known-first-party = ["thoughtflow"]
```

### Example

**Before:**
```python
from thoughtflow import Agent
import os
from typing import Any
import pytest
from thoughtflow.trace import Session
```

**After:**
```python
import os
from typing import Any

import pytest

from thoughtflow import Agent
from thoughtflow.trace import Session
```

---

## Line Length

Default line length is 88 characters (Black-compatible).

### Breaking Long Lines

**Function calls:**
```python
# Before
result = some_function(argument_one, argument_two, argument_three, argument_four)

# After
result = some_function(
    argument_one,
    argument_two,
    argument_three,
    argument_four,
)
```

**Strings:**
```python
# Before
message = "This is a very long string that exceeds the line length limit and needs to be broken"

# After
message = (
    "This is a very long string that exceeds the "
    "line length limit and needs to be broken"
)
```

**Imports:**
```python
# Before
from thoughtflow.adapters import OpenAIAdapter, AnthropicAdapter, LocalAdapter, BedrockAdapter

# After
from thoughtflow.adapters import (
    AnthropicAdapter,
    BedrockAdapter,
    LocalAdapter,
    OpenAIAdapter,
)
```

---

## Pre-commit Integration

Pre-commit runs Ruff automatically on commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

### What Happens on Commit

1. You run `git commit`
2. Pre-commit runs Ruff format
3. Pre-commit runs Ruff check
4. If issues found:
   - Auto-fixable issues are fixed
   - Commit is blocked
   - You re-stage files and commit again

```bash
# Typical workflow
git add .
git commit -m "feat: my feature"
# Ruff runs, fixes issues, blocks commit

# Re-add fixed files
git add .
git commit -m "feat: my feature"
# Success!
```

---

## IDE Integration

### VS Code

1. Install the **Ruff** extension
2. Add to settings.json:

```json
{
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit"
        }
    }
}
```

### PyCharm

Use File Watchers or External Tools (see [03-ide-configuration.md](03-ide-configuration.md)).

---

## Checking Before PR

Run all checks before creating a PR:

```bash
# Format
ruff format src/ tests/

# Lint with fixes
ruff check --fix src/ tests/

# Verify no remaining issues
ruff check src/ tests/
ruff format --check src/ tests/
```

Or use pre-commit:

```bash
pre-commit run --all-files
```

---

## Configuration Reference

Full configuration in `ruff.toml`:

```toml
target-version = "py39"
line-length = 88

[lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
ignore = ["E501"]
fixable = ["ALL"]

[lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ARG001"]
"__init__.py" = ["F401"]

[lint.isort]
known-first-party = ["thoughtflow"]

[format]
quote-style = "double"
indent-style = "space"
```

---

## Troubleshooting

### "Ruff not found"

```bash
pip install ruff
# or
pip install -e ".[dev]"
```

### Different results locally vs CI

Make sure Ruff versions match:

```bash
ruff --version
# Update if needed
pip install --upgrade ruff
```

### Pre-commit hook keeps failing

```bash
# Update pre-commit hooks
pre-commit autoupdate

# Clear cache
pre-commit clean

# Run again
pre-commit run --all-files
```

---

## Next Steps

- [08-type-checking.md](08-type-checking.md) - Fix type errors
- [06-running-tests.md](06-running-tests.md) - Run tests after formatting

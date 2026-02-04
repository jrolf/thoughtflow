# Project Structure

This guide explains the ThoughtFlow codebase layout and where to find things.

---

## Top-Level Overview

```
thoughtflow/
├── .github/                # GitHub-specific files
├── src/                    # Source code (the library)
├── tests/                  # Test suite
├── docs/                   # Documentation
├── examples/               # Example scripts
├── developer/              # Developer guides (you are here!)
├── pyproject.toml          # Project configuration
└── ...                     # Config files
```

---

## Source Code (`src/thoughtflow/`)

The actual library code lives here. This is what gets packaged and published to PyPI.

```
src/thoughtflow/
├── __init__.py             # Package entry point, public API exports
├── py.typed                # Marker for PEP 561 type hints
├── agent.py                # Core Agent class
├── message.py              # Message schema
├── _util.py                # Internal utilities (not public API)
│
├── adapters/               # Provider adapters
│   ├── __init__.py         # Adapter exports
│   ├── base.py             # Adapter interface/protocol
│   ├── openai.py           # OpenAI adapter
│   ├── anthropic.py        # Anthropic adapter
│   └── local.py            # Local model adapter (Ollama)
│
├── tools/                  # Tool system
│   ├── __init__.py
│   ├── base.py             # Tool interface
│   └── registry.py         # Tool registry
│
├── memory/                 # Memory hooks
│   ├── __init__.py
│   └── base.py             # Memory interface
│
├── trace/                  # Tracing/observability
│   ├── __init__.py
│   ├── session.py          # Session object
│   ├── events.py           # Event types
│   └── schema.py           # Schema versioning
│
└── eval/                   # Evaluation utilities
    ├── __init__.py
    ├── replay.py           # Record/replay
    └── harness.py          # Test harness
```

### Key Files to Know

| File | Purpose | When to Edit |
|------|---------|--------------|
| `__init__.py` | Public exports | Adding/removing public API |
| `agent.py` | Core Agent | Changing agent behavior |
| `message.py` | Message format | Changing message schema |
| `adapters/base.py` | Adapter interface | Changing adapter contract |
| `adapters/openai.py` | OpenAI integration | OpenAI-specific changes |

---

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py             # Shared fixtures, test configuration
│
├── unit/                   # Fast, deterministic tests
│   ├── __init__.py
│   ├── test_agent.py       # Tests for agent.py
│   ├── test_message.py     # Tests for message.py
│   └── test_trace.py       # Tests for trace module
│
└── integration/            # Tests requiring external services
    ├── __init__.py
    ├── test_openai_adapter.py
    └── test_anthropic_adapter.py
```

### Test Naming Convention

- Test file: `test_<module_name>.py`
- Test class: `Test<ClassName>`
- Test method: `test_<what_it_tests>`

Example: `test_agent.py` contains `TestAgent` class with `test_agent_requires_adapter` method.

---

## Documentation (`docs/`)

```
docs/
├── index.md                # Homepage
├── quickstart.md           # Getting started guide
├── concepts/               # Concept deep-dives
│   ├── agent.md
│   ├── adapters.md
│   ├── tools.md
│   ├── memory.md
│   └── tracing.md
└── api/                    # Auto-generated API docs
```

Documentation is built with [MkDocs](https://www.mkdocs.org/). See [16-writing-documentation.md](16-writing-documentation.md).

---

## Examples (`examples/`)

Runnable scripts demonstrating ThoughtFlow usage:

```
examples/
├── 01_hello_world.py       # Basic usage
├── 02_tool_use.py          # Using tools
├── 03_memory_hooks.py      # Memory integration
├── 04_trace_replay.py      # Tracing
└── 05_multi_provider.py    # Multiple providers
```

---

## GitHub Configuration (`.github/`)

```
.github/
├── workflows/
│   ├── ci.yml              # CI pipeline (lint, test, type-check)
│   ├── publish.yml         # PyPI publishing
│   └── release.yml         # Release automation
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml
│   └── feature_request.yml
└── PULL_REQUEST_TEMPLATE.md
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool config |
| `ruff.toml` | Linter/formatter configuration |
| `mkdocs.yml` | Documentation site configuration |
| `.pre-commit-config.yaml` | Pre-commit hook configuration |
| `.gitignore` | Files to ignore in Git |
| `.editorconfig` | Editor formatting rules |

---

## Understanding the `src/` Layout

ThoughtFlow uses the **"src layout"**:

```
thoughtflow/           # Project root
└── src/
    └── thoughtflow/   # Actual package
```

### Why `src/` Layout?

1. **Prevents accidental imports**: You can't accidentally import from the project root instead of the installed package
2. **Catches packaging bugs early**: If something isn't packaged correctly, tests fail
3. **Clean separation**: Source code is clearly separated from config files

### How It Works

When you run `pip install -e .`:
- A link is created from `site-packages` to `src/thoughtflow`
- `import thoughtflow` works from anywhere
- Changes to `src/thoughtflow` take effect immediately

---

## Module Dependency Graph

```
                    ┌─────────────────┐
                    │   __init__.py   │  (public API)
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐         ┌─────────┐
   │  agent  │         │ message  │         │  trace  │
   └────┬────┘         └──────────┘         └────┬────┘
        │                                        │
        ▼                                        ▼
   ┌──────────┐                            ┌──────────┐
   │ adapters │                            │   eval   │
   └──────────┘                            └──────────┘
        │
   ┌────┴────┬────────┐
   ▼         ▼        ▼
openai  anthropic   local
```

---

## Finding What You Need

### "Where is the Agent class defined?"
→ `src/thoughtflow/agent.py`

### "Where do I add a new adapter?"
→ Create `src/thoughtflow/adapters/new_adapter.py`

### "Where are the tests for messages?"
→ `tests/unit/test_message.py`

### "How do I add a new example?"
→ Create `examples/XX_description.py`

### "Where is the CI configuration?"
→ `.github/workflows/ci.yml`

---

## Next Steps

- [03-ide-configuration.md](03-ide-configuration.md) - Set up your editor
- [04-branching-workflow.md](04-branching-workflow.md) - Start coding

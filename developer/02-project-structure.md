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
├── llm.py                  # LLM: multi-provider model calls + record/replay
├── embed.py                # EMBED: multi-provider embeddings + record/replay
├── memory.py               # MEMORY: event-sourced state container
├── thought.py              # THOUGHT: prompt + LLM + parsing + validation
├── action.py               # ACTION: imperative operation wrapper
├── tool.py                 # TOOL: LLM-selectable capability with schema
├── agent.py                # AGENT: autonomous tool-use loop
├── mcp.py                  # MCP: Model Context Protocol client
├── workflow.py             # WORKFLOW: flow composition
├── chat.py                 # CHAT: human-in-the-loop conversation
├── message.py              # Message schema helpers
├── _util.py                # Internal utilities (not public API)
│
├── agents/                 # Agent methodology subclasses
│   ├── react.py            # ReactAgent (Reason + Act)
│   ├── reflect.py          # ReflectAgent (critique + revise)
│   └── planact.py          # PlanActAgent (plan then execute)
│
├── thoughts/               # THOUGHT subclasses (DECIDE, PLAN)
├── actions/                # Action primitives (SAY, ASK, SEARCH, FETCH, ...)
│
└── eval/                   # Evaluation utilities
    ├── __init__.py
    └── harness.py          # Test harness (Harness, TestCase)
```

### Key Files to Know

| File | Purpose | When to Edit |
|------|---------|--------------|
| `__init__.py` | Public exports | Adding/removing public API |
| `llm.py` | Provider routing, record/replay | Adding providers, replay changes |
| `memory.py` | Event-sourced state | Changing event/serialization behavior |
| `agent.py` | Core agent loop | Changing agent behavior |
| `thought.py` | Cognition unit | Changing prompt/parse/validate pipeline |

---

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py             # Shared fixtures, test configuration
│
├── unit/                   # Fast, deterministic tests (no network)
│   ├── __init__.py
│   ├── test_llm.py         # Tests for llm.py (monkeypatched transport)
│   ├── test_memory.py      # Tests for memory.py
│   ├── test_agent.py       # Tests for agent.py
│   ├── test_replay.py      # Tests for record/replay
│   └── ...                 # One file per module
│
└── integration/            # Tests requiring external services
    ├── __init__.py
    ├── test_llm_providers.py
    └── ...
```

### Test Naming Convention

- Test file: `test_<module_name>.py`
- Test class: `Test<ClassName>`
- Test method: `test_<what_it_tests>`

Example: `test_llm.py` contains `TestLLMInitialization` class with `test_parses_service_and_model` method.

---

## Documentation (`docs/`)

```
docs/
├── index.md                # Homepage
├── quickstart.md           # Getting started guide
└── concepts/               # Concept deep-dives
    ├── llm.md
    ├── memory.md
    ├── agent.md
    ├── tools.md
    ├── replay.md
    └── rag.md
```

The canonical per-primitive API reference lives in `primitives/` at the repo root (e.g. `primitives/LLM.md`).

Documentation is built with [MkDocs](https://www.mkdocs.org/). See [16-writing-documentation.md](16-writing-documentation.md).

---

## Examples (`examples/`)

Runnable code demonstrating ThoughtFlow usage:

```
examples/
├── scripts/                # Runnable example scripts
├── notebooks1/             # Jupyter notebooks
└── serverless/             # Serverless deployment examples
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
        ┌──────────┬─────────┼──────────┬──────────┐
        │          │         │          │          │
        ▼          ▼         ▼          ▼          ▼
   ┌─────────┐ ┌───────┐ ┌────────┐ ┌────────┐ ┌──────┐
   │ thought │ │ agent │ │ memory │ │ action │ │ eval │
   └────┬────┘ └───┬───┘ └────────┘ └────────┘ └──────┘
        │          │
        │     ┌────┴────┐
        ▼     ▼         ▼
      ┌─────────┐   ┌──────┐
      │   llm   │   │ tool │
      └─────────┘   └──────┘
```

`llm.py` and `embed.py` contain all provider-specific logic — each provider is a `_call_<service>` method, not a separate module.

---

## Finding What You Need

### "Where is the AGENT class defined?"
→ `src/thoughtflow/agent.py`

### "Where do I add a new provider?"
→ Add a `_call_<service>` method in `src/thoughtflow/llm.py` — see [15-adding-providers.md](15-adding-providers.md)

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

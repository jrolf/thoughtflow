# Writing Documentation

This guide explains how to write and build documentation for ThoughtFlow.

---

## Documentation Structure

```
docs/
├── index.md            # Homepage
├── quickstart.md       # Getting started
├── concepts/           # Deep-dive guides
│   ├── agent.md
│   ├── adapters.md
│   └── ...
└── api/               # Auto-generated API docs
```

---

## Building Docs Locally

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve locally with hot reload
mkdocs serve

# Open http://127.0.0.1:8000
```

---

## Writing Guidelines

### Use Clear Language

- Write for developers new to ThoughtFlow
- Avoid jargon without explanation
- Use active voice

### Include Code Examples

```markdown
## Basic Usage

```python
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter

adapter = OpenAIAdapter()
agent = Agent(adapter)
response = agent.call([{"role": "user", "content": "Hello!"}])
```
```

### Document All Public APIs

Every public class/function needs:
- One-line description
- Detailed explanation
- Args/Returns documentation
- Example usage

---

## Docstring Format

Use Google-style docstrings:

```python
def example(arg1: str, arg2: int = 10) -> bool:
    """Short description of what the function does.

    Longer description with more details if needed.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When arg1 is empty.

    Example:
        >>> example("test", 20)
        True
    """
```

---

## Adding New Pages

1. Create the markdown file in `docs/`
2. Add to `mkdocs.yml` navigation:

```yaml
nav:
  - Home: index.md
  - Concepts:
    - New Page: concepts/new-page.md  # Add here
```

3. Preview with `mkdocs serve`

---

## Markdown Tips

### Admonitions

```markdown
!!! note
    This is a note.

!!! warning
    This is a warning.

!!! tip
    This is a tip.
```

### Code with Line Numbers

```markdown
```python linenums="1"
def example():
    return "hello"
```
```

### Tabs

```markdown
=== "Python"
    ```python
    print("Hello")
    ```

=== "Bash"
    ```bash
    echo "Hello"
    ```
```

---

## Updating API Docs

API documentation is auto-generated from docstrings using mkdocstrings:

```yaml
# mkdocs.yml
plugins:
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
```

Reference in docs:
```markdown
::: thoughtflow.Agent
```

---

## Documentation Checklist

- [ ] Clear and concise
- [ ] Code examples work
- [ ] Links are valid
- [ ] Builds without warnings
- [ ] Previewed locally

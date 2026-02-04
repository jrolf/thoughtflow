# Developer Guides

Welcome to the ThoughtFlow developer documentation! These guides provide step-by-step instructions for contributing to ThoughtFlow.

## Getting Started

| Guide | Description |
|-------|-------------|
| [01-environment-setup.md](01-environment-setup.md) | Set up your development environment |
| [02-project-structure.md](02-project-structure.md) | Understand the codebase layout |
| [03-ide-configuration.md](03-ide-configuration.md) | Configure VS Code or PyCharm |

## Daily Development

| Guide | Description |
|-------|-------------|
| [04-branching-workflow.md](04-branching-workflow.md) | Create and manage branches |
| [05-making-commits.md](05-making-commits.md) | Write good commit messages |
| [06-running-tests.md](06-running-tests.md) | Run tests locally |
| [07-linting-formatting.md](07-linting-formatting.md) | Format code and fix lint errors |
| [08-type-checking.md](08-type-checking.md) | Run mypy and fix type errors |

## Contributing

| Guide | Description |
|-------|-------------|
| [09-creating-pull-requests.md](09-creating-pull-requests.md) | Submit your changes |
| [10-code-review.md](10-code-review.md) | Participate in code reviews |
| [11-merge-conflicts.md](11-merge-conflicts.md) | Resolve merge conflicts |

## Writing Code

| Guide | Description |
|-------|-------------|
| [12-writing-tests.md](12-writing-tests.md) | Write effective tests |
| [13-adding-features.md](13-adding-features.md) | Add new functionality |
| [14-fixing-bugs.md](14-fixing-bugs.md) | Debug and fix issues |
| [15-adding-adapters.md](15-adding-adapters.md) | Create new provider adapters |

## Documentation & Quality

| Guide | Description |
|-------|-------------|
| [16-writing-documentation.md](16-writing-documentation.md) | Write and build docs |
| [17-debugging-tips.md](17-debugging-tips.md) | Debug ThoughtFlow code |

## Maintenance

| Guide | Description |
|-------|-------------|
| [18-dependency-management.md](18-dependency-management.md) | Update dependencies |
| [19-release-process.md](19-release-process.md) | Release workflow (maintainers) |
| [20-troubleshooting.md](20-troubleshooting.md) | Common issues and solutions |

---

## Quick Reference

### Most Common Commands

```bash
# Run tests
pytest tests/unit/ -v

# Format code
ruff format src/ tests/

# Check lint
ruff check src/ tests/

# Type check
mypy src/

# Build docs
mkdocs serve
```

### Before Every PR

```bash
# Run the full pre-commit check
pre-commit run --all-files

# Or run each step manually
ruff format src/ tests/
ruff check src/ tests/
mypy src/
pytest tests/unit/ -v
```

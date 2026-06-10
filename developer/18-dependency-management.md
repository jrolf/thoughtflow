# Dependency Management

Managing dependencies in ThoughtFlow.

---

## Dependency Philosophy

ThoughtFlow has **zero core dependencies**. Provider integrations are built on the standard library (`urllib`, `json`), so they add no dependencies either. The only extras are for development and documentation tooling.

---

## Dependency Types

### Core Dependencies

```toml
[project]
dependencies = []  # None!
```

### Optional Dependencies

```toml
[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.1", "mypy>=1.0"]
docs = ["mkdocs>=1.5", "mkdocs-material>=9.0"]
```

---

## Adding Dependencies

### For Core (Rare)

The zero-dependency constraint is a design pillar, not a preference. New providers and primitives must be implemented with the standard library — see [15-adding-providers.md](15-adding-providers.md). Adding a core dependency requires maintainer sign-off:

```toml
[project]
dependencies = [
    "new-essential-dep>=1.0",  # Almost never
]
```

### For Tooling

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "new-dev-tool>=1.0",  # Add here
]
```

---

## Updating Dependencies

### Check Outdated

```bash
pip list --outdated
```

### Update Dev Dependencies

```toml
# pyproject.toml
dev = [
    "pytest>=8.0",  # Updated
    "ruff>=0.2",    # Updated
]
```

### Update Lock File (if used)

```bash
pip-compile pyproject.toml
```

---

## Version Constraints

| Constraint | Meaning |
|------------|---------|
| `>=1.0` | 1.0 or higher |
| `>=1.0,<2.0` | 1.x only |
| `~=1.4` | >=1.4, <2.0 |
| `==1.4.2` | Exact (avoid) |

### Best Practices

- Use `>=` for flexibility
- Add upper bound for breaking APIs: `>=1.0,<3.0`
- Avoid exact pins in libraries

---

## Testing Compatibility

```yaml
# .github/workflows/ci.yml
strategy:
  matrix:
    python-version: ["3.9", "3.10", "3.11", "3.12"]
```

---

## Security Updates

Check for vulnerabilities:

```bash
pip install pip-audit
pip-audit
```

Update vulnerable packages immediately.

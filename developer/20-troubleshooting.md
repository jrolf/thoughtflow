# Troubleshooting

Common issues and solutions.

---

## Installation Issues

### "Module not found"

```bash
# Ensure installed
pip install -e ".[dev]"

# Check installation
pip show thoughtflow
```

### Permission Errors (Windows)

Run terminal as Administrator, or:
```bash
python -m pip install -e ".[dev]"
```

### SSL Certificate Errors

```bash
pip install --upgrade pip certifi
```

---

## Development Issues

### Tests Not Running

```bash
# Check pytest is installed
pytest --version

# Reinstall
pip install -e ".[dev]"
```

### Pre-commit Fails

```bash
# Update hooks
pre-commit autoupdate

# Clear cache
pre-commit clean

# Run manually
pre-commit run --all-files
```

### Import Errors in IDE

1. Check Python interpreter is set to `.venv`
2. Restart IDE/reload window
3. Reinstall: `pip install -e ".[dev]"`

---

## Git Issues

### "Permission denied (publickey)"

```bash
# Check SSH key
ssh -T git@github.com

# If fails, add key:
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub
# Add to GitHub settings
```

### Can't Push to Fork

```bash
# Check remote
git remote -v

# Should show origin as YOUR fork
git remote set-url origin git@github.com:YOUR_USERNAME/thoughtflow.git
```

---

## CI/CD Issues

### CI Fails But Local Passes

1. Check Python version matches CI
2. Run exact CI commands locally
3. Check for OS-specific issues

### Tests Pass Locally, Fail in CI

```bash
# Match CI environment
python -m venv .ci-test
source .ci-test/bin/activate
pip install -e ".[dev]"
pytest tests/unit/ -v
```

---

## Type Checking Issues

### "Cannot find implementation"

```bash
pip install types-<package>
```

### Circular Import

Use `TYPE_CHECKING`:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .other import Other
```

---

## Getting Help

1. Search existing GitHub issues
2. Check this troubleshooting guide
3. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details
4. Ask in GitHub Discussions

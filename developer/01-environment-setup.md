# Environment Setup

This guide walks you through setting up your local development environment for ThoughtFlow.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.9+** installed
- **Git** installed
- **GitHub account** with SSH keys configured
- A code editor (VS Code or PyCharm recommended)

### Check Your Python Version

```bash
python --version
# Should show Python 3.9.x or higher
```

If you need to install Python, visit [python.org](https://www.python.org/downloads/) or use a version manager like `pyenv`.

---

## Step 1: Fork the Repository

1. Go to https://github.com/jrolf/thoughtflow
2. Click the **Fork** button (top right)
3. This creates a copy under your GitHub account

---

## Step 2: Clone Your Fork

```bash
# Clone your fork (replace YOUR_USERNAME)
git clone git@github.com:YOUR_USERNAME/thoughtflow.git

# Or using HTTPS
git clone https://github.com/YOUR_USERNAME/thoughtflow.git

# Navigate into the project
cd thoughtflow
```

---

## Step 3: Add Upstream Remote

This lets you pull updates from the main repository:

```bash
# Add the original repo as "upstream"
git remote add upstream https://github.com/jrolf/thoughtflow.git

# Verify remotes
git remote -v
# Should show:
# origin    git@github.com:YOUR_USERNAME/thoughtflow.git (fetch)
# origin    git@github.com:YOUR_USERNAME/thoughtflow.git (push)
# upstream  https://github.com/jrolf/thoughtflow.git (fetch)
# upstream  https://github.com/jrolf/thoughtflow.git (push)
```

---

## Step 4: Create a Virtual Environment

**Always use a virtual environment** to isolate dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Your prompt should now show (.venv)
```

### Verify Activation

```bash
which python
# Should show: /path/to/thoughtflow/.venv/bin/python
```

---

## Step 5: Install Dependencies

```bash
# Install ThoughtFlow in editable mode with all dev dependencies
pip install -e ".[dev]"

# This installs:
# - ThoughtFlow (editable, so changes take effect immediately)
# - pytest, pytest-cov (testing)
# - ruff (linting/formatting)
# - mypy (type checking)
# - pre-commit (git hooks)
```

### Verify Installation

```bash
# Check ThoughtFlow is installed
python -c "import thoughtflow; print(thoughtflow.__version__)"

# Check tools are available
pytest --version
ruff --version
mypy --version
```

---

## Step 6: Install Pre-commit Hooks

Pre-commit hooks run automatically before each commit to catch issues early:

```bash
# Install the hooks
pre-commit install

# Verify installation
pre-commit --version

# (Optional) Run hooks on all files now
pre-commit run --all-files
```

---

## Step 7: Verify Everything Works

Run the test suite to make sure everything is set up correctly:

```bash
# Run unit tests
pytest tests/unit/ -v

# Expected output: All tests should pass (or show NotImplementedError for placeholders)
```

---

## Step 8: (Optional) Install Provider Dependencies

If you're working on specific adapters:

```bash
# For OpenAI adapter development
pip install -e ".[openai]"

# For Anthropic adapter development
pip install -e ".[anthropic]"

# For all providers
pip install -e ".[all-providers]"

# For everything (dev + docs + all providers)
pip install -e ".[all]"
```

---

## Step 9: (Optional) Set Up API Keys

For integration testing, set environment variables:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Reload your shell or source the file
source ~/.zshrc
```

**Never commit API keys to the repository!**

---

## Directory Structure After Setup

```
thoughtflow/
├── .venv/                  # Your virtual environment
├── .git/                   # Git repository
├── src/thoughtflow/        # Source code (this is what you edit)
├── tests/                  # Test files
├── docs/                   # Documentation
├── examples/               # Example scripts
└── ...
```

---

## Keeping Your Fork Updated

Periodically sync with upstream:

```bash
# Fetch upstream changes
git fetch upstream

# Switch to your main branch
git checkout main

# Merge upstream changes
git merge upstream/main

# Push to your fork
git push origin main
```

---

## Troubleshooting

### "Command not found" errors

Make sure your virtual environment is activated:
```bash
source .venv/bin/activate
```

### Permission errors on Windows

Try running your terminal as Administrator, or use:
```bash
python -m pip install -e ".[dev]"
```

### SSL certificate errors

Try upgrading pip and certifi:
```bash
pip install --upgrade pip certifi
```

---

## Next Steps

- [02-project-structure.md](02-project-structure.md) - Understand the codebase
- [03-ide-configuration.md](03-ide-configuration.md) - Set up your editor
- [04-branching-workflow.md](04-branching-workflow.md) - Start making changes

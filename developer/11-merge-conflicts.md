# Resolving Merge Conflicts

This guide explains how to resolve merge conflicts when they occur.

---

## What Are Merge Conflicts?

Merge conflicts happen when:
- You and someone else changed the same lines
- Git can't automatically determine which change to keep
- Manual intervention is required

---

## Detecting Conflicts

### During Rebase

```bash
git fetch upstream
git rebase upstream/main
# CONFLICT (content): Merge conflict in src/thoughtflow/agent.py
# error: could not apply abc1234... feat: my feature
```

### During Merge

```bash
git merge upstream/main
# Auto-merging src/thoughtflow/agent.py
# CONFLICT (content): Merge conflict in src/thoughtflow/agent.py
# Automatic merge failed; fix conflicts and then commit the result.
```

### In a PR

GitHub shows: "This branch has conflicts that must be resolved"

---

## Understanding Conflict Markers

Git marks conflicts in files like this:

```python
def example():
<<<<<<< HEAD
    return "your version"
=======
    return "their version"
>>>>>>> upstream/main
```

| Marker | Meaning |
|--------|---------|
| `<<<<<<< HEAD` | Start of your changes |
| `=======` | Separator |
| `>>>>>>> upstream/main` | End of their changes |

---

## Resolving Conflicts

### Method 1: Using VS Code (Recommended)

VS Code shows conflicts with helpful buttons:

1. Open the conflicted file
2. You'll see options above each conflict:
   - **Accept Current Change** - Keep your version
   - **Accept Incoming Change** - Keep their version
   - **Accept Both Changes** - Keep both
   - **Compare Changes** - See side by side
3. Click the appropriate option
4. Save the file

### Method 2: Manual Resolution

1. Open the conflicted file in any editor
2. Find the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
3. Decide what the final code should be
4. Remove the conflict markers
5. Save the file

**Example:**

Before (conflict):
```python
def get_version():
<<<<<<< HEAD
    return "1.0.0"
=======
    return "1.1.0"
>>>>>>> upstream/main
```

After (resolved - keeping newer version):
```python
def get_version():
    return "1.1.0"
```

After (resolved - combining both):
```python
def get_version():
    # Updated from 1.0.0 to 1.1.0
    return "1.1.0"
```

### Method 3: Using Git Commands

```bash
# Keep your version entirely
git checkout --ours src/thoughtflow/agent.py

# Keep their version entirely
git checkout --theirs src/thoughtflow/agent.py
```

---

## After Resolving Conflicts

### For Rebase

```bash
# Mark file as resolved
git add src/thoughtflow/agent.py

# Continue rebase
git rebase --continue

# If more conflicts, repeat the process

# If you want to abort and start over
git rebase --abort
```

### For Merge

```bash
# Mark file as resolved
git add src/thoughtflow/agent.py

# Commit the merge
git commit -m "Merge upstream/main and resolve conflicts"
```

### Push Your Changes

```bash
# If you rebased, force push is needed
git push --force-with-lease

# If you merged, regular push works
git push
```

---

## Resolving Conflicts on GitHub

For simple conflicts, GitHub offers a web editor:

1. Click "Resolve conflicts" button on PR
2. Edit the file in the browser
3. Remove conflict markers
4. Click "Mark as resolved"
5. Click "Commit merge"

**Limitation:** Only works for text conflicts, not complex ones.

---

## Common Conflict Scenarios

### Scenario 1: Both Changed Same Function

```python
<<<<<<< HEAD
def process(data: dict) -> str:
    """Process data and return result."""
    return str(data)
=======
def process(data: dict[str, Any]) -> str:
    """Process the input data."""
    result = json.dumps(data)
    return result
>>>>>>> upstream/main
```

**Resolution:** Combine the improvements:
```python
def process(data: dict[str, Any]) -> str:
    """Process data and return result."""
    result = json.dumps(data)
    return result
```

### Scenario 2: You Deleted, They Modified

```python
<<<<<<< HEAD
# (empty - you deleted this)
=======
def old_function():
    """This function was modified upstream."""
    return "new implementation"
>>>>>>> upstream/main
```

**Resolution:** Decide if the function is still needed. If not, keep your deletion. If yes, keep their version.

### Scenario 3: Import Conflicts

```python
<<<<<<< HEAD
from thoughtflow import Agent, Message
from thoughtflow.trace import Session
=======
from thoughtflow import Agent
from thoughtflow.adapters import OpenAIAdapter
>>>>>>> upstream/main
```

**Resolution:** Merge the imports:
```python
from thoughtflow import Agent, Message
from thoughtflow.adapters import OpenAIAdapter
from thoughtflow.trace import Session
```

### Scenario 4: pyproject.toml Version Conflicts

```toml
[project]
<<<<<<< HEAD
version = "0.2.0"
=======
version = "0.2.1"
>>>>>>> upstream/main
```

**Resolution:** Usually keep the higher version from upstream.

---

## Avoiding Conflicts

### Keep Your Branch Updated

```bash
# Regularly sync with upstream
git fetch upstream
git rebase upstream/main
```

### Make Small, Focused PRs

- Smaller changes = fewer conflicts
- Faster reviews = less time for conflicts to develop

### Communicate

- If working on same area as someone else, coordinate
- Mention in PR if related to other work

---

## Complex Conflict Resolution

### When Multiple Files Conflict

```bash
git status
# Shows all conflicted files

# Resolve each one
# Then:
git add .
git rebase --continue
```

### When Conflicts Are Too Complex

```bash
# Abort the rebase/merge
git rebase --abort
# or
git merge --abort

# Start fresh
git checkout main
git fetch upstream
git checkout -b feature/my-feature-v2
# Cherry-pick or reimplement your changes
```

### Getting Help

If you're stuck:
1. Don't force push broken code
2. Ask for help in PR comments
3. Share the conflict details
4. A maintainer can help resolve

---

## Tools for Conflict Resolution

### VS Code

Built-in merge conflict viewer with:
- Side-by-side comparison
- One-click resolution buttons
- Inline diff highlighting

### Git Mergetool

```bash
# Configure a merge tool
git config --global merge.tool vimdiff

# Launch it
git mergetool
```

### Sourcetree / GitKraken / GitHub Desktop

GUI tools with visual conflict resolution.

---

## Best Practices

### Do

- ✅ Resolve conflicts carefully - don't lose changes
- ✅ Run tests after resolving
- ✅ Review the final result
- ✅ Ask for help if unsure

### Don't

- ❌ Blindly accept one side
- ❌ Push without testing
- ❌ Delete conflict markers without resolving
- ❌ Panic - conflicts are normal!

---

## Verification After Resolution

```bash
# Check status (should be clean)
git status

# Run tests
pytest tests/unit/ -v

# Check formatting
ruff format --check src/ tests/

# Check lint
ruff check src/ tests/

# If all good, push
git push --force-with-lease  # if rebased
git push  # if merged
```

---

## Next Steps

- [04-branching-workflow.md](04-branching-workflow.md) - Branch management
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your PR

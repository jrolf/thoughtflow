# Making Commits

This guide explains how to write good commit messages and organize your commits.

---

## Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Examples

```
feat(adapters): add AWS Bedrock adapter

fix(trace): prevent duplicate events when session is reused

docs(readme): add Windows installation instructions

test(tools): add tests for ToolRegistry.unregister()

refactor(agent): simplify call() method signature

chore(deps): update ruff to 0.2.0
```

---

## Commit Types

| Type | When to Use | Appears in Changelog |
|------|-------------|---------------------|
| `feat` | New feature | ✅ Yes |
| `fix` | Bug fix | ✅ Yes |
| `docs` | Documentation only | ❌ No |
| `style` | Formatting (no code change) | ❌ No |
| `refactor` | Code change (no new feature or fix) | ❌ No |
| `test` | Adding or updating tests | ❌ No |
| `chore` | Maintenance (deps, config) | ❌ No |
| `perf` | Performance improvement | ✅ Yes |
| `ci` | CI/CD changes | ❌ No |
| `build` | Build system changes | ❌ No |
| `revert` | Reverting a previous commit | ✅ Yes |

---

## Scopes

Scopes help identify what part of the codebase is affected:

| Scope | Description |
|-------|-------------|
| `agent` | Agent module |
| `message` | Message module |
| `adapters` | Adapter system |
| `openai` | OpenAI adapter specifically |
| `anthropic` | Anthropic adapter specifically |
| `tools` | Tool system |
| `memory` | Memory system |
| `trace` | Tracing system |
| `eval` | Evaluation utilities |
| `deps` | Dependencies |
| `ci` | CI/CD configuration |
| `docs` | Documentation |

Scope is optional but recommended.

---

## Writing Good Descriptions

### Do

- Use imperative mood ("add" not "added" or "adds")
- Keep under 72 characters
- Start with lowercase
- No period at the end

### Don't

- Don't explain *what* changed (that's visible in the diff)
- Don't be vague ("fix bug", "update code")
- Don't include issue numbers in the title

### Good Examples

```
feat(adapters): add streaming support to OpenAI adapter
fix(trace): handle None values in event serialization
docs(quickstart): clarify virtual environment setup
test(agent): add tests for TracedAgent wrapper
refactor(tools): extract common validation logic
```

### Bad Examples

```
Fixed the bug                    # Too vague
Add feature                      # Too vague
Updated openai.py               # Describes file, not change
feat: Add streaming support.    # Has period
FEAT(adapters): Add streaming   # Wrong case
```

---

## Commit Body

For complex changes, add a body explaining **why** the change was made:

```
fix(trace): prevent memory leak in long-running sessions

The Session object was holding references to all events without
any cleanup mechanism. For long-running processes, this caused
memory usage to grow unboundedly.

This change adds an optional max_events parameter that triggers
automatic cleanup of old events when exceeded.
```

### When to Include a Body

- The change isn't obvious from the diff
- There are design decisions to explain
- The fix addresses a specific bug/issue
- There are caveats or limitations

---

## Referencing Issues

Reference issues in the footer, not the title:

```
feat(adapters): add support for custom headers

Allow users to pass custom headers to the underlying HTTP client.
This is useful for corporate proxies and custom authentication.

Closes #42
```

Keywords that close issues:
- `Closes #123`
- `Fixes #123`
- `Resolves #123`

---

## Breaking Changes

For breaking changes, add `!` after the type and explain in the footer:

```
feat(agent)!: change call() signature to require params

BREAKING CHANGE: The `params` argument is now required in Agent.call().
Previously it was optional with a default of None.

Migration:
  Before: agent.call(messages)
  After:  agent.call(messages, params={})
```

---

## Atomic Commits

Each commit should be a single logical change:

### Good: Atomic Commits

```
commit 1: feat(tools): add Tool base class
commit 2: feat(tools): add ToolResult class
commit 3: feat(tools): add ToolRegistry
commit 4: test(tools): add tests for Tool and ToolRegistry
commit 5: docs(tools): add tool documentation
```

### Bad: Monolithic Commit

```
commit 1: Add entire tool system with tests and docs
```

### Bad: Too Granular

```
commit 1: Add Tool class
commit 2: Add docstring to Tool class
commit 3: Fix typo in docstring
commit 4: Add name attribute to Tool
commit 5: Add description attribute to Tool
```

---

## Staging Changes

### Stage Specific Files

```bash
# Stage one file
git add src/thoughtflow/agent.py

# Stage multiple files
git add src/thoughtflow/agent.py tests/unit/test_agent.py

# Stage all Python files
git add "*.py"
```

### Stage Parts of a File

```bash
# Interactive staging (choose hunks)
git add -p src/thoughtflow/agent.py

# Then press:
# y - stage this hunk
# n - skip this hunk
# s - split into smaller hunks
# q - quit
```

### Unstage Changes

```bash
# Unstage a file (keep changes)
git restore --staged src/thoughtflow/agent.py

# Unstage all files
git restore --staged .
```

---

## Amending Commits

### Fix the Last Commit Message

```bash
git commit --amend -m "feat(agent): correct message here"
```

### Add Forgotten Changes to Last Commit

```bash
# Stage the forgotten changes
git add forgotten_file.py

# Amend without changing message
git commit --amend --no-edit
```

**Warning**: Only amend commits that haven't been pushed!

---

## Interactive Rebase

Clean up commits before creating a PR:

```bash
# Rebase last 3 commits
git rebase -i HEAD~3
```

This opens an editor:

```
pick abc1234 feat(tools): add Tool class
pick def5678 fix typo
pick ghi9012 feat(tools): add ToolRegistry

# Commands:
# p, pick = use commit
# r, reword = use commit, but edit message
# e, edit = use commit, but stop to amend
# s, squash = meld into previous commit
# f, fixup = like squash, but discard message
# d, drop = remove commit
```

### Common Operations

**Squash "fix typo" into previous commit:**
```
pick abc1234 feat(tools): add Tool class
fixup def5678 fix typo
pick ghi9012 feat(tools): add ToolRegistry
```

**Reword a commit message:**
```
reword abc1234 feat(tools): add Tool class
pick def5678 fix typo
pick ghi9012 feat(tools): add ToolRegistry
```

---

## Pre-commit Hooks

Pre-commit hooks run automatically when you commit:

```bash
# If a hook fails, fix the issue and try again
git add .
git commit -m "feat: my feature"
# Hook runs, finds issue, commit blocked

# Fix the issue
ruff format src/

# Try again
git add .
git commit -m "feat: my feature"
# Success!
```

### Skip Hooks (Emergency Only)

```bash
git commit --no-verify -m "wip: work in progress"
```

**Don't do this** unless absolutely necessary. Fix the issues instead.

---

## Commit Workflow Summary

```bash
# 1. Make changes to files

# 2. Check what changed
git status
git diff

# 3. Stage changes
git add src/thoughtflow/agent.py
git add tests/unit/test_agent.py

# 4. Verify staging
git status

# 5. Commit with good message
git commit -m "feat(agent): add retry parameter to call()"

# 6. If you need to fix something
git add forgotten.py
git commit --amend --no-edit

# 7. Push when ready
git push
```

---

## Next Steps

- [06-running-tests.md](06-running-tests.md) - Run tests before committing
- [07-linting-formatting.md](07-linting-formatting.md) - Format your code
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your work

# Branching Workflow

This guide explains how to create and manage branches for your contributions.

---

## Overview

```
main (upstream) ──●──●──●──●──●──●──●──●──
                          ↑
                          │ merge
                          │
feature/my-feature ───────●──●──●
                          ↑
                          │ branch from
                          │
main (your fork) ─────────●──●──●──●
```

---

## Step 1: Sync Your Fork

Before starting new work, always sync with upstream:

```bash
# Switch to main
git checkout main

# Fetch upstream changes
git fetch upstream

# Merge upstream into your main
git merge upstream/main

# Push to your fork
git push origin main
```

---

## Step 2: Create a Feature Branch

**Always create a new branch for your work.** Never commit directly to `main`.

### Branch Naming Convention

```
<type>/<short-description>
```

Types:
- `feature/` - New functionality
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code restructuring
- `test/` - Adding tests

Examples:
```bash
# Good branch names
feature/add-bedrock-adapter
fix/message-serialization-error
docs/improve-quickstart
refactor/simplify-trace-events
test/add-tool-registry-tests

# Bad branch names
my-changes
update
fix
```

### Create the Branch

```bash
# Create and switch to new branch
git checkout -b feature/my-new-feature

# Verify you're on the new branch
git branch
# * feature/my-new-feature
#   main
```

---

## Step 3: Make Your Changes

Now you can edit files, add features, fix bugs, etc.

```bash
# Check status frequently
git status

# See what you've changed
git diff

# Stage specific files
git add src/thoughtflow/agent.py

# Or stage all changes
git add .
```

---

## Step 4: Commit Your Changes

See [05-making-commits.md](05-making-commits.md) for detailed commit guidelines.

```bash
# Commit with a descriptive message
git commit -m "feat(agent): add retry capability to Agent.call()"
```

---

## Step 5: Push Your Branch

```bash
# First push (sets upstream)
git push -u origin feature/my-new-feature

# Subsequent pushes
git push
```

---

## Step 6: Keep Your Branch Updated

If `main` has been updated while you're working:

```bash
# Fetch latest from upstream
git fetch upstream

# Rebase your branch onto upstream/main
git rebase upstream/main

# If there are conflicts, resolve them, then:
git rebase --continue

# Force push (needed after rebase)
git push --force-with-lease
```

### Why Rebase Instead of Merge?

Rebasing creates a cleaner history by putting your commits on top of the latest `main`, rather than creating merge commits.

---

## Common Branch Operations

### List Branches

```bash
# Local branches
git branch

# All branches (including remote)
git branch -a

# With last commit info
git branch -v
```

### Switch Between Branches

```bash
# Switch to an existing branch
git checkout main
git checkout feature/my-new-feature

# Or use the newer syntax
git switch main
git switch feature/my-new-feature
```

### Delete a Branch

```bash
# Delete local branch (after merging)
git branch -d feature/my-new-feature

# Force delete (if not merged)
git branch -D feature/my-new-feature

# Delete remote branch
git push origin --delete feature/my-new-feature
```

### Rename a Branch

```bash
# Rename current branch
git branch -m new-name

# Rename a different branch
git branch -m old-name new-name
```

---

## Working on Multiple Features

You can have multiple branches at once:

```bash
# Start feature A
git checkout main
git checkout -b feature/feature-a
# ... work on A ...
git commit -m "feat: add feature A"

# Pause A, start feature B
git checkout main
git checkout -b feature/feature-b
# ... work on B ...
git commit -m "feat: add feature B"

# Go back to A
git checkout feature/feature-a
# ... continue working on A ...
```

---

## Stashing Changes

If you need to switch branches but have uncommitted changes:

```bash
# Stash current changes
git stash

# Switch branches
git checkout other-branch
# ... do something ...

# Go back and restore changes
git checkout feature/my-feature
git stash pop
```

### Stash Commands

```bash
# List stashes
git stash list

# Apply most recent stash (keep in list)
git stash apply

# Apply and remove from list
git stash pop

# Apply a specific stash
git stash apply stash@{2}

# Drop a stash
git stash drop stash@{0}

# Clear all stashes
git stash clear
```

---

## Emergency: Wrong Branch!

### Committed to Wrong Branch

```bash
# You accidentally committed to main instead of a feature branch

# Create the feature branch at current commit
git branch feature/my-feature

# Reset main to before your commit
git reset --hard HEAD~1

# Switch to feature branch
git checkout feature/my-feature
```

### Started Work Without Creating Branch

```bash
# You have uncommitted changes on main

# Create and switch to new branch (keeps changes)
git checkout -b feature/my-feature

# Now commit normally
git add .
git commit -m "feat: my changes"
```

---

## Branch Protection

The `main` branch is protected:
- Direct pushes are not allowed
- All changes must go through pull requests
- CI must pass before merging
- At least one review is required

---

## Workflow Summary

```bash
# 1. Sync fork
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# 2. Create branch
git checkout -b feature/my-feature

# 3. Make changes and commit
git add .
git commit -m "feat: description"

# 4. Push branch
git push -u origin feature/my-feature

# 5. Create PR on GitHub

# 6. After merge, clean up
git checkout main
git branch -d feature/my-feature
```

---

## Next Steps

- [05-making-commits.md](05-making-commits.md) - Write good commits
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Submit your PR

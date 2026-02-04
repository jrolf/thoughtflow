# Creating Pull Requests

This guide walks you through creating and submitting a pull request.

---

## Before Creating a PR

### Checklist

Run these commands and ensure all pass:

```bash
# Format code
ruff format src/ tests/

# Check lint
ruff check src/ tests/

# Type check
mypy src/

# Run tests
pytest tests/unit/ -v

# Or run everything with pre-commit
pre-commit run --all-files
```

### Ensure Branch is Up to Date

```bash
# Fetch latest upstream
git fetch upstream

# Rebase on latest main
git rebase upstream/main

# Resolve any conflicts if needed

# Push (force if rebased)
git push --force-with-lease
```

---

## Creating the PR

### Step 1: Push Your Branch

```bash
git push -u origin feature/my-feature
```

### Step 2: Open GitHub

Go to either:
- Your fork: `https://github.com/YOUR_USERNAME/thoughtflow`
- The main repo: `https://github.com/jrolf/thoughtflow`

You'll see a banner: "feature/my-feature had recent pushes"

### Step 3: Click "Compare & pull request"

Or go to **Pull requests** → **New pull request**

### Step 4: Select Branches

- **base repository**: `jrolf/thoughtflow`
- **base**: `main`
- **head repository**: `YOUR_USERNAME/thoughtflow`
- **compare**: `feature/my-feature`

---

## Writing the PR Description

### Use the Template

The PR template will appear automatically:

```markdown
## Description

<!-- Describe your changes in detail -->

## Related Issue

<!-- Link to the issue this PR addresses -->
Fixes #

## Type of Change

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 💥 Breaking change
- [ ] 📝 Documentation update
- [ ] 🧹 Refactoring
- [ ] 🧪 Test update

## Checklist

### Code Quality
- [ ] My code follows the project's style guidelines
- [ ] I have run `ruff format` and `ruff check`
- [ ] I have run `mypy` and fixed any type errors

### Testing
- [ ] I have added tests that prove my fix/feature works
- [ ] All existing tests pass locally

### Documentation
- [ ] I have updated the documentation accordingly
- [ ] I have updated the CHANGELOG.md (if applicable)

### ThoughtFlow Principles
- [ ] My changes maintain a small API surface
- [ ] My changes keep state explicit
- [ ] My changes support deterministic testing
```

### Good PR Title

Follow commit message format:

```
feat(adapters): add AWS Bedrock adapter
fix(trace): prevent duplicate events in session
docs(quickstart): add Windows installation instructions
```

### Good PR Description

```markdown
## Description

Adds a new adapter for AWS Bedrock, allowing ThoughtFlow to work with
Amazon's managed LLM service. The adapter supports:
- Claude models via Bedrock
- Titan models
- Streaming responses

## Related Issue

Fixes #42

## Type of Change

- [ ] 🐛 Bug fix
- [x] ✨ New feature
- [ ] 💥 Breaking change

## Implementation Details

The adapter uses boto3 to communicate with Bedrock. It follows the same
pattern as other adapters:
- Lazy client initialization
- Message format translation
- Capability reporting

## Testing

- Added unit tests for BedrockAdapter
- Tested manually with Claude on Bedrock
- Integration tests are skipped without AWS credentials
```

---

## After Creating the PR

### CI Will Run

GitHub Actions automatically runs:
1. Linting (Ruff)
2. Type checking (mypy)
3. Tests (pytest) across Python 3.9-3.12

Wait for all checks to pass (green checkmarks).

### Address CI Failures

If CI fails:

1. Click on the failed check to see logs
2. Fix the issue locally
3. Push the fix:

```bash
git add .
git commit -m "fix: address CI feedback"
git push
```

The PR will update automatically.

---

## Code Review Process

### What to Expect

1. **Automated feedback** - CI results
2. **Maintainer review** - Usually within a few days
3. **Feedback** - Comments on specific lines or general suggestions
4. **Approval** - When changes look good

### Responding to Feedback

**For code changes:**

```bash
# Make requested changes
git add .
git commit -m "fix: address review feedback"
git push
```

**For discussions:**
- Reply to comments directly on GitHub
- Use "Resolve conversation" when addressed
- Ask for clarification if needed

### Requesting Re-review

After addressing feedback:
1. Push your changes
2. Reply to conversations
3. Click "Re-request review" (circular arrow icon)

---

## PR Etiquette

### Do

- ✅ Keep PRs focused (one feature/fix per PR)
- ✅ Respond to feedback promptly
- ✅ Be open to suggestions
- ✅ Test your changes thoroughly
- ✅ Update the PR description if scope changes

### Don't

- ❌ Create massive PRs (hard to review)
- ❌ Mix unrelated changes
- ❌ Ignore CI failures
- ❌ Force push after review has started (loses comments)
- ❌ Get defensive about feedback

---

## Draft PRs

For work in progress, create a draft PR:

1. Create PR normally
2. Click "Create draft pull request" instead of "Create pull request"

Benefits:
- Gets early feedback
- Shows you're working on something
- CI still runs
- Won't be merged accidentally

Convert to ready when done:
- Click "Ready for review"

---

## Keeping PR Updated

If main changes while your PR is open:

```bash
# Fetch latest
git fetch upstream

# Rebase
git rebase upstream/main

# Resolve conflicts if any
# Edit files, then:
git add .
git rebase --continue

# Push (force needed after rebase)
git push --force-with-lease
```

### Merge Conflicts in PR

If GitHub shows "This branch has conflicts":

1. Click "Resolve conflicts" on GitHub (for simple conflicts)
2. Or resolve locally (recommended for complex conflicts)

---

## After PR is Merged

### Clean Up

```bash
# Switch to main
git checkout main

# Update your main
git fetch upstream
git merge upstream/main
git push origin main

# Delete your feature branch locally
git branch -d feature/my-feature

# Delete remote branch (if not auto-deleted)
git push origin --delete feature/my-feature
```

### Celebrate! 🎉

Your contribution is now part of ThoughtFlow!

---

## Common Scenarios

### PR Needs Changes Before Review

```bash
# Make changes
git add .
git commit -m "fix: update based on self-review"
git push
```

### Squashing Commits

If asked to squash commits:

```bash
# Squash last 3 commits into one
git rebase -i HEAD~3

# Mark commits as 'squash' or 'fixup'
# Save and edit the combined commit message

# Force push
git push --force-with-lease
```

### Reverting a Commit

If you need to undo something:

```bash
# Revert specific commit
git revert <commit-hash>
git push
```

---

## Troubleshooting

### "Branch is out of date"

```bash
git fetch upstream
git rebase upstream/main
git push --force-with-lease
```

### CI Keeps Failing

1. Run checks locally: `pre-commit run --all-files`
2. Check specific failures in CI logs
3. Ask for help in the PR comments

### Reviewer Not Responding

- Wait 3-5 business days
- Leave a polite comment asking for review
- Ping maintainers if urgent

---

## Next Steps

- [10-code-review.md](10-code-review.md) - Participate in reviews
- [11-merge-conflicts.md](11-merge-conflicts.md) - Handle conflicts

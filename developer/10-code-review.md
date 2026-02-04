# Code Review

This guide explains how to participate in code reviews, both as an author and a reviewer.

---

## As a PR Author

### Preparing for Review

Before requesting review:

1. **Self-review first** - Read through your own changes
2. **Run all checks** - Ensure CI will pass
3. **Write clear description** - Explain what and why
4. **Keep it focused** - One feature/fix per PR

### Responding to Feedback

**Types of feedback:**

| Icon | Meaning | Action Required |
|------|---------|-----------------|
| 💭 | Comment | Consider, respond |
| 🔧 | Suggestion | Implement or discuss |
| ❓ | Question | Answer |
| ⚠️ | Concern | Address before merge |
| ❌ | Request changes | Must fix |

### How to Respond

**Agree with feedback:**
```
Good catch! Fixed in abc1234.
```

**Disagree respectfully:**
```
I considered that approach, but chose this because [reason].
What do you think about [alternative]?
```

**Need clarification:**
```
Could you elaborate on what you mean by [X]?
I want to make sure I understand correctly.
```

**Implementing suggestions:**

GitHub has a "Commit suggestion" button for simple changes:
1. Click the button
2. Review the change
3. Click "Commit suggestion"

For complex changes:
```bash
# Make the change locally
git add .
git commit -m "fix: address review - [description]"
git push
```

### Resolving Conversations

After addressing feedback:
1. Reply explaining what you changed
2. Click "Resolve conversation"

**Don't** resolve without responding - reviewers may have follow-up questions.

---

## As a Reviewer

### Getting Started

1. Go to **Pull requests** tab
2. Click on a PR to review
3. Click **Files changed** to see the diff

### Review Checklist

**Code Quality:**
- [ ] Code is readable and well-organized
- [ ] Names are clear and descriptive
- [ ] No obvious bugs or edge cases missed
- [ ] Error handling is appropriate

**Tests:**
- [ ] Tests cover the new functionality
- [ ] Tests are readable and focused
- [ ] Edge cases are tested

**Documentation:**
- [ ] Docstrings are present and accurate
- [ ] README/docs updated if needed
- [ ] CHANGELOG updated for features/fixes

**ThoughtFlow Principles:**
- [ ] Maintains small API surface
- [ ] State is explicit (no hidden side effects)
- [ ] Supports deterministic testing
- [ ] Portable across providers

### Leaving Comments

**Inline comments** - Click the `+` on any line:

```
This could be simplified using a list comprehension:
`python
result = [item.process() for item in items]
`
```

**Suggestions** - Use the suggestion syntax for direct fixes:

```suggestion
result = [item.process() for item in items]
```

The author can then commit this directly with one click.

### Comment Types

**Praise (important!):**
```
🎉 Nice! This is a clean solution.
```

**Question:**
```
❓ What happens if `items` is empty here?
```

**Suggestion:**
```
💡 Consider using a dataclass instead of a dict for better type safety.
```

**Concern:**
```
⚠️ This might cause a race condition if called from multiple threads.
Could we add a lock here?
```

**Required change:**
```
🚫 This will break the public API. We need to deprecate first:
1. Add deprecation warning in this version
2. Remove in next major version
```

### Submitting Your Review

1. Click **Review changes** (top right)
2. Write a summary
3. Choose:
   - **Comment** - General feedback, no approval needed
   - **Approve** - Changes look good
   - **Request changes** - Must be addressed before merge
4. Click **Submit review**

### Review Summary Examples

**Approving:**
```
LGTM! 🚀

Nice clean implementation. Just one optional suggestion for the docstring,
but feel free to merge as-is.
```

**Requesting changes:**
```
Good progress! A few things to address before this is ready:

1. The error handling in `process()` needs to catch specific exceptions
2. Missing test for the empty input case
3. Type annotation missing on `get_result()`

Let me know if you have questions!
```

**Comment only:**
```
Interesting approach! Left some questions for my own understanding.
Not blocking - just curious about the design decisions.
```

---

## Review Best Practices

### Do

- ✅ Be timely (review within 2-3 days)
- ✅ Be specific (point to exact lines)
- ✅ Explain the "why" behind suggestions
- ✅ Acknowledge good work
- ✅ Offer alternatives, not just criticism
- ✅ Use questions when unsure

### Don't

- ❌ Be harsh or dismissive
- ❌ Nitpick style issues (that's what Ruff is for)
- ❌ Block on personal preference
- ❌ Ignore the PR for weeks
- ❌ Request major rewrites without discussion

### Tone Matters

**Instead of:**
```
This is wrong. Use X instead.
```

**Try:**
```
Have you considered using X here? It might be more efficient because [reason].
```

**Instead of:**
```
Why did you do it this way?
```

**Try:**
```
I'm curious about this approach - what led you to this design?
There might be context I'm missing.
```

---

## Handling Disagreements

### As Author

1. Explain your reasoning
2. Ask for clarification
3. Propose alternatives
4. If stuck, ask a maintainer to weigh in

### As Reviewer

1. Listen to the author's reasoning
2. Distinguish "must fix" from "nice to have"
3. Be willing to learn something new
4. Escalate to maintainer if needed

### Example Discussion

**Reviewer:**
```
I think we should use a class instead of a dict here for type safety.
```

**Author:**
```
I considered that, but using a dict keeps the API simpler for users who
just want to pass JSON directly from their config files. What if we
accept both? Users could pass a dict or a Config class.
```

**Reviewer:**
```
That's a good point about user convenience. Accepting both sounds like
a good compromise. Could you add a note in the docstring about both options?
```

---

## Approving and Merging

### Who Can Merge

- Only maintainers can merge PRs
- At least one approval is required
- CI must pass

### Merge Strategies

- **Squash and merge** (default) - All commits become one
- **Rebase and merge** - Commits are applied individually
- **Create a merge commit** - Creates a merge commit

ThoughtFlow uses **squash and merge** by default to keep history clean.

### After Approval

1. Author addresses any final comments
2. Maintainer merges the PR
3. Author deletes their branch (optional)

---

## Finding PRs to Review

### Good First Reviews

Look for:
- `good first issue` label
- Small PRs (< 200 lines)
- Documentation changes
- Test additions

### Review Queue

Go to: `https://github.com/jrolf/thoughtflow/pulls`

Filter by:
- `review-requested:@me` - Requested for you
- `status:open` - Open PRs
- `label:needs-review` - Awaiting review

---

## Learning from Reviews

### As Author

- Note recurring feedback patterns
- Ask questions if you don't understand
- Thank reviewers for their time

### As Reviewer

- Read other reviewers' comments
- Learn from maintainer feedback
- Review PRs outside your expertise to learn

---

## Next Steps

- [11-merge-conflicts.md](11-merge-conflicts.md) - Handle conflicts
- [09-creating-pull-requests.md](09-creating-pull-requests.md) - Create your own PR

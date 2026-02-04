# Release Process

How releases are made (maintainers only).

---

## Version Numbering

We use [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- `0.x.x` = Pre-stable, breaking changes allowed
- `x.0.0` = Major (breaking changes)
- `x.x.0` = Minor (new features)
- `x.x.x` = Patch (bug fixes)

---

## Release Checklist

### 1. Prepare Release Branch

```bash
git checkout main
git pull upstream main
git checkout -b release/0.2.0
```

### 2. Update Version

```toml
# pyproject.toml
version = "0.2.0"
```

### 3. Update CHANGELOG

```markdown
## [0.2.0] - 2025-01-30

### Added
- New feature X

### Fixed
- Bug Y
```

### 4. Create PR

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: prepare release 0.2.0"
git push origin release/0.2.0
```

Create PR to `main`.

### 5. After Merge, Tag

```bash
git checkout main
git pull upstream main
git tag v0.2.0
git push upstream v0.2.0
```

### 6. Automated Publishing

The `publish.yml` workflow:
1. Runs tests
2. Builds package
3. Publishes to TestPyPI
4. Publishes to PyPI
5. Creates GitHub Release

---

## PyPI Trusted Publishing

ThoughtFlow uses OIDC trusted publishing (no API tokens):

1. Go to https://pypi.org/manage/project/thoughtflow/settings/publishing/
2. Add GitHub publisher:
   - Owner: `jrolf`
   - Repository: `thoughtflow`
   - Workflow: `publish.yml`
   - Environment: `pypi`

---

## Hotfix Releases

For urgent fixes:

```bash
git checkout main
git checkout -b fix/critical-bug
# Fix the bug
git commit -m "fix: critical bug"
# Fast-track review and merge
git tag v0.1.1
git push upstream v0.1.1
```

---

## Post-Release

- [ ] Verify package on PyPI
- [ ] Test installation: `pip install thoughtflow==0.2.0`
- [ ] Update documentation site
- [ ] Announce release

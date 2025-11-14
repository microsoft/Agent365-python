# How to Set a Version

This document describes how to manage versioning for the Microsoft Agent 365 Python SDK, whether you're creating development builds or official releases.

## Branch Strategy

The repository follows a specific branch strategy for releases:

- **`main` branch**: Active development, always contains dev versions (e.g., `0.1.0dev5`)
- **`release/*` branches**: Official releases, where tags are created and packages are published
- **Feature branches**: Development work, merges into `main`

**Important:** Official releases and package publishing **only** happen on `release/*` branches, never on `main`.

## Overview

This repository uses **`setuptools-git-versioning`** to automatically calculate version numbers based on Git history. The version is determined by:
- The base version in `versioning/TARGET-VERSION`
- The number of commits since that file was last modified
- Whether the current commit has a Git tag
- The branch where the commit exists (release branches vs. main/feature branches)

## Version Format

All versions follow [PEP 440](https://peps.python.org/pep-0440/) format:

- **Development versions**: `0.1.0dev5` (base version + dev + commit count)
- **Release versions**: `0.1.0` (exact version from Git tag)

**Where versions are generated:**
- `main` and feature branches → Development versions with `dev` suffix
- `release/*` branches with Git tags → Official release versions without `dev` suffix

---

## Development Builds

Development builds are created automatically for any commit that doesn't have a release tag. These builds include a `dev` suffix to clearly indicate they are not official releases.

### When You Get a Dev Version

A development version is generated in these scenarios:

1. **After making commits to the repository**
   - Each commit increments the dev counter
   - Example: `0.1.0dev1`, `0.1.0dev2`, `0.1.0dev3`, etc.

2. **When working on feature branches**
   - All commits get dev versions based on commit count

3. **In CI/CD pipelines**
   - Pull requests and branch pushes automatically get dev versions

### How to Build a Dev Version Locally

1. **Check your current version:**
   ```powershell
   .\replace-version.ps1
   ```
   Or on Linux/Mac:
   ```bash
   cd versioning
   python -m setuptools_git_versioning
   ```

2. **Build packages with the dev version:**
   ```bash
   # The version is automatically calculated during build
   uv build --all-packages --wheel
   ```

3. **Example output:**
   ```
   Package version: 0.1.0dev7
   Building: microsoft-agents-a365-runtime-0.1.0dev7-py3-none-any.whl
   ```

### How CI Creates Dev Versions

The CI pipeline automatically:
1. Checks out the full Git history (`fetch-depth: 0`)
2. Runs `setuptools-git-versioning` in the `versioning/` directory
3. Sets the `AGENT365_PYTHON_SDK_PACKAGE_VERSION` environment variable
4. Builds all packages with that version

**No manual intervention needed!**

---

## Official Release Builds

Official releases are created by tagging specific commits **on `release/*` branches**. Once tagged, that commit produces an exact version number without the `dev` suffix.

> **Important:** Official builds and publishing to package repositories should only happen from `release/*` branches, not from `main`.

### Prerequisites for Creating a Release

Before creating an official release, ensure:
- [ ] All intended changes are merged to `main`
- [ ] All tests pass in CI on `main`
- [ ] Documentation is updated
- [ ] Changelog is updated (if applicable)
- [ ] You have write permissions to create release branches and tags

### Step-by-Step: Creating an Official Release

#### Step 1: Create a Release Branch

Official releases must be done from a `release/*` branch:

1. **Checkout and update `main`:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a release branch:**
   ```bash
   # For version 0.2.0
   git checkout -b release/0.2.0
   ```

3. **Update `versioning/TARGET-VERSION`:**
   ```bash
   # For version 0.2.0
   echo "0.2.0." > versioning/TARGET-VERSION
   ```

4. **Commit the version file change:**
   ```bash
   git add versioning/TARGET-VERSION
   git commit -m "Bump version to 0.2.0"
   ```

5. **Push the release branch:**
   ```bash
   git push origin release/0.2.0
   ```

6. **Wait for CI to pass** on the release branch

> **Note:** After this commit, new commits will produce versions like `0.2.0dev0`, `0.2.0dev1`, etc.

#### Step 2: Create and Push the Release Tag

1. **Ensure you're on the release branch:**
   ```bash
   git checkout release/0.2.0
   git pull origin release/0.2.0
   ```

2. **Create an annotated Git tag on the release branch:**
   ```bash
   # For version 0.2.0
   git tag -a v0.2.0 -m "Release version 0.2.0"
   ```

   **Tag naming convention:** `v{MAJOR}.{MINOR}.{PATCH}`
   - Use semantic versioning
   - Always prefix with `v`
   - Examples: `v0.1.0`, `v1.0.0`, `v1.2.3`
   - **Must be created on a `release/*` branch**

3. **Push the tag to the remote repository:**
   ```bash
   git push origin v0.2.0
   ```

> **Note:** The CI pipeline will only publish packages when tags are pushed on `release/*` branches.

#### Step 3: Verify the Release Version

1. **Check out the tagged commit:**
   ```bash
   git checkout v0.2.0
   ```

2. **Verify the version:**
   ```powershell
   .\replace-version.ps1
   ```
   
   **Expected output:** `0.2.0` (no `dev` suffix)

3. **Build packages:**
   ```bash
   uv build --all-packages --wheel
   ```
   
   **Expected output:**
   ```
   Package version: 0.2.0
   Building: microsoft-agents-a365-runtime-0.2.0-py3-none-any.whl
   ```

#### Step 4: Publish to Package Repository

Once the official build is created, the CI pipeline will automatically publish to your package repository when the tag is pushed on a `release/*` branch.

```bash
# The CI pipeline does this automatically for release/* branches with tags
# To manually publish (if needed):
uv run twine upload dist/*.whl
```

#### Step 5: Merge Release Branch Back (Optional)

After a successful release, you may want to merge the release branch back to `main`:

```bash
git checkout main
git merge release/0.2.0
git push origin main
```

---

## Common Scenarios

### Scenario 1: Patch Release (Bug Fix)

You want to release version `0.1.1` after `0.1.0`:

1. Create release branch: `git checkout -b release/0.1.1`
2. Update `versioning/TARGET-VERSION` to `0.1.1.`
3. Commit and push: `git push origin release/0.1.1`
4. Create and push tag: `git tag -a v0.1.1 -m "Release 0.1.1 - Bug fixes"`
5. Push tag: `git push origin v0.1.1`

### Scenario 2: Minor Release (New Features)

You want to release version `0.2.0` after `0.1.5`:

1. Create release branch: `git checkout -b release/0.2.0`
2. Update `versioning/TARGET-VERSION` to `0.2.0.`
3. Commit and push: `git push origin release/0.2.0`
4. Create and push tag: `git tag -a v0.2.0 -m "Release 0.2.0 - New features"`
5. Push tag: `git push origin v0.2.0`

### Scenario 3: Major Release (Breaking Changes)

You want to release version `1.0.0`:

1. Create release branch: `git checkout -b release/1.0.0`
2. Update `versioning/TARGET-VERSION` to `1.0.0.`
3. Commit and push: `git push origin release/1.0.0`
4. Create and push tag: `git tag -a v1.0.0 -m "Release 1.0.0 - First stable release"`
5. Push tag: `git push origin v1.0.0`

### Scenario 4: Continue Development After Release

After releasing `0.2.0` on `release/0.2.0` branch, you want to continue development on `main` for `0.3.0`:

1. Checkout main: `git checkout main`
2. Update `versioning/TARGET-VERSION` to `0.3.0.`
3. Commit and push to main
4. Next commit automatically becomes `0.3.0dev0`
5. Subsequent commits increment: `0.3.0dev1`, `0.3.0dev2`, etc.

### Scenario 5: Hotfix on a Release Branch

You need to create a hotfix `0.2.1` after `0.2.0` has been released:

1. Checkout the release branch: `git checkout release/0.2.0`
2. Create a new branch for the hotfix: `git checkout -b release/0.2.1`
3. Apply your fixes and commit them
4. Update `versioning/TARGET-VERSION` to `0.2.1.`
5. Commit and push: `git push origin release/0.2.1`
6. Create and push tag: `git tag -a v0.2.1 -m "Release 0.2.1 - Hotfix"`
7. Push tag: `git push origin v0.2.1`
8. Merge back to main: `git checkout main && git merge release/0.2.1`

---

## Troubleshooting

### Problem: Version shows `0.0.0`

**Cause:** The `AGENT365_PYTHON_SDK_PACKAGE_VERSION` environment variable is not set.

**Solution:**
```bash
# Set the environment variable before building
cd versioning
export AGENT365_PYTHON_SDK_PACKAGE_VERSION=$(python -m setuptools_git_versioning)
cd ..
uv build --all-packages --wheel
```

### Problem: Version doesn't match expectations

**Cause:** Git history might be incomplete (shallow clone).

**Solution:**
```bash
# Fetch full Git history
git fetch --unshallow
```

### Problem: Dev counter doesn't reset after updating TARGET-VERSION

**Cause:** The `TARGET-VERSION` file wasn't actually committed or modified.

**Solution:**
1. Verify the file change is committed: `git log versioning/TARGET-VERSION`
2. Ensure `count_commits_from_version_file = true` in `versioning/pyproject.toml`

### Problem: Tagged version still shows `dev` suffix

**Cause:** You're not on the tagged commit, or the tag wasn't created properly.

**Solution:**
```bash
# Check you're on the tagged commit
git describe --tags --exact-match

# If not, checkout the tag
git checkout v0.2.0

# Verify tag exists
git tag -l "v0.2.0"
```

---

## Best Practices

### ✅ DO:
- **Create release branches**: Always use `release/*` branches for official releases
- Always use annotated tags: `git tag -a v1.0.0 -m "Message"`
- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update `TARGET-VERSION` before tagging for new releases
- Test builds locally before pushing tags
- Document releases in changelog/release notes
- Merge release branches back to `main` after successful releases

### ❌ DON'T:
- **Tag `main` branch for releases**: Official releases must be on `release/*` branches
- Use lightweight tags: `git tag v1.0.0` (missing `-a`)
- Manually edit version numbers in code
- Delete and recreate tags (causes confusion)
- Skip version numbers (e.g., jump from 0.1.0 to 0.3.0)
- Forget to push tags: `git push --tags`
- Create releases directly on `main` branch

---

## Quick Reference

| Action | Command |
|--------|---------|
| Check current version | `.\replace-version.ps1` or `cd versioning && python -m setuptools_git_versioning` |
| Create release branch | `git checkout -b release/0.2.0` |
| Update base version | Edit `versioning/TARGET-VERSION` |
| Create release tag | `git tag -a v0.2.0 -m "Release 0.2.0"` |
| Push tag | `git push origin v0.2.0` |
| Push release branch | `git push origin release/0.2.0` |
| List all tags | `git tag -l` |
| List release branches | `git branch -r \| grep release/` |
| Delete local tag | `git tag -d v0.2.0` |
| Delete remote tag | `git push origin :refs/tags/v0.2.0` |
| Build packages | `uv build --all-packages --wheel` |
| View tag details | `git show v0.2.0` |
| Merge release to main | `git checkout main && git merge release/0.2.0` |

---

## Additional Resources

- [PEP 440 - Version Identification](https://peps.python.org/pep-0440/)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [setuptools-git-versioning Documentation](https://setuptools-git-versioning.readthedocs.io/)
- [Git Tagging Documentation](https://git-scm.com/book/en/v2/Git-Basics-Tagging)

---

## Support

If you encounter issues with versioning:
1. Check this document's Troubleshooting section
2. Verify your Git setup with `git log` and `git describe`
3. Check CI logs for version calculation errors
4. Open an issue with version output and Git status


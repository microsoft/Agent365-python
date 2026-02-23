---
name: commit
description: Use this skill when the user wants to commit staged changes. This skill checks linting, then formatting (matching CI order), runs tests, generates a commit message, and commits the changes. Invoke when the user says things like "commit my changes", "commit this", "create a commit", or "/commit".
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Commit Skill

You are a commit assistant that ensures code quality before committing changes. Follow these steps in order, stopping if any step fails.

## Step 1: Check for Staged Changes

First, verify there are staged changes to commit:

```bash
git diff --cached --stat
```

If there are no staged changes, inform the user and stop. Suggest they stage changes with `git add`.

## Step 2: Check Linting

Run the linting check first (matches CI order in .github/workflows/ci.yml):

```bash
uv run --frozen ruff check .
```

### If linting check fails:

1. Inform the user about the linting errors
2. Ask if they want you to auto-fix what can be auto-fixed
3. If yes, run: `uv run --frozen ruff check . --fix`
4. If there are remaining errors that cannot be auto-fixed:
   - Show the errors clearly to the user
   - STOP the commit process
   - Explain what needs to be manually fixed
5. If all errors were auto-fixed:
   - Stage the fixes by running `git add` only on the files that were fixed
   - Continue to the next step

### If linting check passes:
Continue to the next step.

## Step 3: Check Code Formatting

Run the formatting check (after linting, matches CI order):

```bash
uv run --frozen ruff format --check .
```

### If formatting check fails:

1. Inform the user that formatting issues were found
2. Ask if they want you to auto-fix the formatting issues
3. If yes, run: `uv run --frozen ruff format .`
4. Show the user what files were reformatted
5. Stage the formatting fixes by running `git add` only on the files that were reformatted
6. Continue to the next step

### If formatting check passes:
Continue to the next step.

## Step 4: Re-verify After Auto-fixes

**IMPORTANT**: If any auto-fixes were applied in Steps 2 or 3, re-run both checks to ensure consistency:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

This prevents commits that pass locally but fail CI (e.g., lint fixes that introduce formatting issues). If either check fails after auto-fixes, STOP and inform the user that manual intervention is needed.

If no auto-fixes were applied, skip this step.

## Step 5: Run Tests

Run the unit tests (excluding integration tests):

```bash
uv run --frozen pytest tests/ -v --tb=short -m "not integration" 2>&1
```

### If tests fail:

1. STOP the commit process immediately
2. Show the test failures clearly to the user
3. Point out:
   - Which test file(s) failed
   - The specific test function(s) that failed
   - The error message and traceback
4. Suggest what might need to be fixed
5. Do NOT proceed with the commit

### If tests pass:
Continue to the next step.

## Step 6: Generate Commit Message

Analyze the staged changes to generate an appropriate commit message:

1. Run `git diff --cached` to see the actual code changes
2. Run `git diff --cached --stat` to see which files changed
3. Check recent commit history for style: `git log --oneline -10`

Generate a commit message following these guidelines:

- **First line**: Concise summary (50 chars or less if possible, max 72)
  - Use imperative mood ("Add feature" not "Added feature")
  - Capitalize the first letter
  - No period at the end
- **Body** (if needed): Explain the "why" not the "what"
  - Wrap at 72 characters
  - Separate from subject with a blank line
- **Footer**: Always include the co-author line

Types of changes to identify:
- `Add` - New feature or file
- `Fix` - Bug fix
- `Update` - Enhancement to existing feature
- `Refactor` - Code restructuring without behavior change
- `Remove` - Deleting code or features
- `Docs` - Documentation only
- `Test` - Adding or updating tests
- `Chore` - Maintenance tasks

## Step 7: Confirm and Commit

1. Show the user the proposed commit message
2. Ask if they want to proceed with this message or modify it
3. If they want to modify, let them provide changes
4. Create the commit using a HEREDOC for proper formatting:

```bash
git commit -m "$(cat <<'EOF'
<commit subject line>

<optional body>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

5. After committing, run `git status` to confirm success
6. Show the user the commit hash and summary

## Important Notes

- NEVER skip any of the quality checks (format, lint, test)
- NEVER use `--no-verify` or similar flags to bypass hooks
- NEVER commit if tests are failing
- ALWAYS include the Co-Authored-By footer
- If the user wants to commit despite failures, politely decline and explain why quality gates matter
- If tests are slow, inform the user they're running but don't skip them

## Error Recovery

If any step fails unexpectedly (not due to code quality issues):
1. Show the error to the user
2. Suggest potential fixes
3. Do not attempt to work around the error by skipping checks

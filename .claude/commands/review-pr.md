# Review Pull Request

Review code changes in a specific pull request using a comprehensive multi-agent code review process.

## Usage

```
/review-pr <PR_NUMBER>
```

**Examples:**
- `/review-pr 123` - Review pull request #123
- `/review-pr 45` - Review pull request #45

## Instructions

You are coordinating a comprehensive code review for pull request #$ARGUMENTS.

### Step 1: Gather PR Information

First, collect information about the pull request:

1. Get PR details and changed files:
   ```bash
   gh pr view $ARGUMENTS --json number,title,body,baseRefName,headRefName,url,files
   gh pr diff $ARGUMENTS
   ```

2. Extract the list of changed files and the PR URL for linking in review comments.

3. **IMPORTANT**: Save the diff output - you will need it to include relevant diff context snippets in each finding.

4. Create the `.codereviews/` directory if it doesn't exist.

### Step 2: Launch Parallel Code Reviews

Launch THREE sub-agents in parallel using the Task tool. Each agent MUST receive:
- The PR number: $ARGUMENTS
- The list of changed files (so they stay scoped to PR files only)
- The PR URL for generating clickable links

**CRITICAL**: You MUST launch all three agents in a SINGLE message with THREE parallel Task tool calls:

1. **architecture-reviewer** (`subagent_type: architecture-reviewer`)
   - Prompt: "Review PR #$ARGUMENTS for architectural concerns. Files changed: [list files]. PR URL: [url]. Focus on design alignment, component boundaries, and documentation gaps. Output your review in the structured markdown format specified in your instructions."

2. **code-reviewer** (`subagent_type: code-reviewer`)
   - Prompt: "Review PR #$ARGUMENTS for code quality. Files changed: [list files]. PR URL: [url]. Focus on Python best practices, SDK usage, security, and maintainability. Output your review in the structured markdown format specified in your instructions."

3. **test-coverage-reviewer** (`subagent_type: test-coverage-reviewer`)
   - Prompt: "Review PR #$ARGUMENTS for test coverage. Files changed: [list files]. PR URL: [url]. Identify missing test scenarios and evaluate existing test quality. Output your review in the structured markdown format specified in your instructions."

### Step 3: Consolidate Reviews

After all three agents complete, consolidate their findings into a single report:

1. **Merge findings** - Combine all issues from the three agents
2. **Deduplicate** - Remove redundant findings, noting when multiple agents identified the same issue
3. **Prioritize** - Sort by severity: Critical → High → Medium → Low
4. **Renumber** - Assign sequential IDs: CRM-001, CRM-002, etc.

### Step 4: Write the Review Report

Write the consolidated review to a markdown file using the Write tool:

**File path**: `.codereviews/claude-pr$ARGUMENTS-<yyyyMMdd_HHmmss>.md`

Use this exact format:

```markdown
# Code Review Report

---

## Review Metadata

```
PR Number:           #$ARGUMENTS
PR Title:            [title from gh pr view]
PR Iteration:        1
Review Date/Time:    [ISO 8601 timestamp]
Reviewer:            code-review-manager
Subagents Used:      architecture-reviewer, code-reviewer, test-coverage-reviewer
```

---

## Overview

[Brief summary of what was reviewed and overall assessment]

---

## Files Reviewed

- `path/to/file1.py`
- `path/to/file2.py`

---

## Findings

### Critical Issues

[Consolidated critical issues with structured format]

### High Priority Issues

[Consolidated high priority issues]

### Medium Priority Issues

[Consolidated medium priority issues]

### Low Priority Issues

[Consolidated low priority issues]

---

## Positive Observations

[What was done well across all review dimensions]

---

## Recommendations

[Prioritized, actionable next steps]

---

## Approval Status

**Final Status:** [APPROVED / APPROVED WITH MINOR NOTES / CHANGES REQUESTED / REJECTED]
```

### Structured Issue Format

For EVERY finding, use this structure:

```markdown
#### [CRM-001] Issue Title

| Field | Value |
|-------|-------|
| **Identified By** | `architecture-reviewer` / `code-reviewer` / `test-coverage-reviewer` / `multiple` |
| **File** | `full/path/to/filename.py` |
| **Line(s)** | 42-58 |
| **Severity** | `critical` / `high` / `medium` / `low` |
| **PR Link** | [View in PR](https://github.com/.../pull/$ARGUMENTS/files#...) |
| **Opened** | [ISO 8601 timestamp] |
| **Resolved** | - [ ] No |
| **Resolution** | _pending_ |
| **Agent Resolvable** | Yes / No / Partial |

**Description:**
[Detailed explanation of the issue]

**Diff Context:**
IMPORTANT: Include the relevant diff snippet from the PR that shows the code being discussed. This makes the review self-contained - readers should understand the issue without needing to look at the PR.
```diff
- old code line (what was removed or changed)
+ new code line (what was added or changed to)
```

**Suggestion:**
[Specific recommendation]
```

### Step 5: Report to User

After writing the review file, inform the user:
1. The path to the review file
2. A summary of findings by severity count
3. The overall approval status

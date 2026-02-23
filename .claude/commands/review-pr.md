# Review Pull Request

Review code changes in a specific pull request using a comprehensive multi-agent code review process with specialized reviewers for architecture, code quality, and test coverage.

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

1. Get PR details, changed files, and the HEAD commit SHA:
   ```bash
   if [ -z "$ARGUMENTS" ]; then
     echo "Error: Missing PR number. Usage: /review-pr <PR_NUMBER>" >&2
     exit 1
   fi
   
   if ! printf '%s\n' "$ARGUMENTS" | grep -Eq '^[0-9]+$'; then
     echo "Error: Invalid PR number '$ARGUMENTS'. PR number must be a positive integer. Usage: /review-pr <PR_NUMBER>" >&2
     exit 1
   fi
   
   gh pr view "$ARGUMENTS" --json number,title,body,baseRefName,headRefName,headRefOid,url,files
   gh pr diff "$ARGUMENTS"
   ```

2. Extract key information:
   - List of changed files
   - PR URL for linking in review comments
   - **HEAD commit SHA** (`headRefOid`) - required for posting inline comments

3. **IMPORTANT**: Save the diff output - you will need it to:
   - Include relevant diff context snippets in each finding
   - Determine the exact **target file line numbers** for inline comments (absolute line numbers in the target file, computed from the diff hunk headers, as required by `/post-review-comments`)
   - Determine the **side** (RIGHT for additions `+`, LEFT for deletions `-`)

4. Create the `.codereviews/` directory if it doesn't exist.

### Step 2: Launch Parallel Code Reviews

Launch THREE sub-agents in parallel using the Task tool. Each agent MUST receive:
- The PR number: $ARGUMENTS
- The list of changed files (so they stay scoped to PR files only)
- The PR URL for generating clickable links

**CRITICAL**: You MUST launch all three agents in a SINGLE message with THREE parallel Task tool calls:

1. **architecture-reviewer** (`subagent_type: architecture-reviewer`)
   - Prompt: "Review PR #$ARGUMENTS for architectural concerns. Files changed: [list files]. PR URL: [url]. Focus on design alignment, component boundaries, namespace patterns, and documentation gaps. Output your review in the structured markdown format specified in your instructions."

2. **code-reviewer** (`subagent_type: code-reviewer`)
   - Prompt: "Review PR #$ARGUMENTS for code quality. Files changed: [list files]. PR URL: [url]. Focus on Python best practices, SDK usage, security, type hints, async patterns, and maintainability. Output your review in the structured markdown format specified in your instructions."

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

````markdown
# Code Review Report

---

## Review Metadata

```
PR Number:           #$ARGUMENTS
PR Title:            [title from gh pr view]
PR Iteration:        1
Review Date/Time:    [ISO 8601 timestamp]
HEAD Commit:         [headRefOid from gh pr view - required for inline comments]
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
````

### Structured Issue Format

For EVERY finding, use this structure:

````markdown
#### [CRM-001] Issue Title

| Field | Value |
|-------|-------|
| **Identified By** | `architecture-reviewer` / `code-reviewer` / `test-coverage-reviewer` / `multiple` |
| **File** | `full/path/to/filename.py` |
| **Line(s)** | 42-58 |
| **Diff Line** | 47 |
| **Diff Side** | RIGHT |
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
````

### Inline Comment Fields Explained

The following fields are **required** for posting inline comments on the PR:

| Field | Description | Example |
|-------|-------------|---------|
| **File** | The exact path to the file as it appears in the diff | `libraries/microsoft-agents-a365-runtime/src/microsoft_agents_a365/runtime/utils.py` |
| **Diff Line** | The **absolute line number** in the target file where the comment should appear. For multi-line issues, use the **last line** of the relevant code block. You can compute this from the diff hunk header plus the line's position within the hunk. | `47` |
| **Diff Side** | Which side of the diff: `RIGHT` for added/modified lines (`+`), `LEFT` for removed lines (`-`). Most comments should be on `RIGHT`. | `RIGHT` |

**How to determine Diff Line:**
1. Look at the diff hunk header (e.g., `@@ -10,5 +10,8 @@`). The number after `+` (`10` in this example) is the starting line in the **new** file; the number after `-` is the starting line in the **old** file.
2. In the hunk body, locate the exact line you want to comment on and determine its offset from the first line of the hunk (counting all context and added/removed lines above it).
3. Add this offset to the starting line from the appropriate side of the header: use the `+` side for `RIGHT` comments (new file), and the `-` side for `LEFT` comments (old file). This sum is the absolute `Diff Line` value.
4. For additions (`+` lines), this means starting from the line number shown after the `+` in the hunk header; for removals (`-` lines), start from the line number shown after the `-`.

**Example:**
```diff
@@ -45,6 +45,9 @@ def initialize_telemetry(self):
         tracer = get_tracer()
+        # Configure span processor
+        span_processor = BatchSpanProcessor(exporter)
+        tracer_provider.add_span_processor(span_processor)
         return tracer_provider
```
For a comment on the `tracer_provider.add_span_processor` line:
- **File**: `libraries/microsoft-agents-a365-observability-core/src/microsoft_agents_a365/observability/core/telemetry.py`
- **Diff Line**: `48` (line 45 + 3 new lines)
- **Diff Side**: `RIGHT` (it's an addition)

### Step 5: Report to User

After writing the review file, inform the user:
1. The path to the review file
2. A summary of findings by severity count
3. The overall approval status
4. Remind them about `/resolve-review` if there are agent-resolvable issues
5. Remind them about `/post-review-comments` to post findings as inline PR comments

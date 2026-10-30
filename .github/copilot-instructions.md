# GitHub Copilot Instructions for Agent365-python

## Package and Release Scope

This repository contains eight packages for Notifications, Runtime, Tooling, and
five Tooling framework adapters. Observability is retired here; do not reintroduce
its packages, imports, tests, or dependency edges. Follow the
[migration guide](../docs/observability-migration.md) for `microsoft-opentelemetry`.
Preserve historical changelogs. Build into a fresh directory and run
`scripts/verify_release_artifacts.py DIRECTORY --version VERSION` before any
artifact promotion or upload; never reuse old `dist/*` release inputs.

## Code Review Rules

### Rule 1: Check for "Kairo" Keyword
- **Description**: Scan code for any occurrence of the keyword "Kairo"
- **Action**: If "Kairo" is found in any code file:
  - Flag it for review
  - Suggest removal or replacement with appropriate terminology
  - Check if it's a legacy reference that needs to be updated
- **Files to check**: All `.py` files in the repository

### Rule 2: Verify Copyright Headers
- **Description**: Ensure all Python files have proper Microsoft copyright headers
- **Action**: If a `.py` file is missing a copyright header:
  - Add the Microsoft copyright header at the top of the file
  - The header should be placed before any imports or code
  - Maintain proper formatting and spacing

#### Required Copyright Header Format
```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```

### Implementation Guidelines

#### When Reviewing Code:
1. **Kairo Check**:
   - Search for case-insensitive matches of "Kairo"
   - Review context to determine if it's:
     - A variable name
     - A comment reference
     - An import statement
     - A string literal
   - Suggest appropriate alternatives based on the context

2. **Header Check**:
   - Verify the first non-empty, non-shebang lines of Python files
   - If missing, prepend the copyright header
   - Ensure there's a blank line after the header before other content
   - Do not add headers to:
     - `__init__.py` files that are intentionally empty
     - Generated files (if marked as such)

#### Example of Proper File Structure:
```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Module docstring goes here."""

import os
import sys

# Rest of the code...
```

### Auto-fix Behavior
When Copilot detects violations:
- **Kairo keyword**: Suggest inline replacement or flag for manual review
- **Missing header**: Automatically suggest adding the copyright header

### Exclusions
- Test files in `tests/` directory may have relaxed header requirements (but headers are still recommended)
- Third-party code or vendored dependencies should not be modified
- Configuration files (`.toml`, `.json`, `.yaml`, `.md`) do not require Python copyright headers

# Product Requirements Document: Centralized Package Version Constraints

**Document Version:** 1.2
**Created:** 2026-01-27
**Status:** Draft
**Author:** Engineering Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Objectives](#2-objectives)
3. [User Stories](#3-user-stories)
4. [Functional Requirements](#4-functional-requirements)
5. [Technical Requirements](#5-technical-requirements)
6. [Package Impact Analysis](#6-package-impact-analysis)
7. [Configuration Design](#7-configuration-design)
8. [Testing Strategy](#8-testing-strategy)
9. [Acceptance Criteria](#9-acceptance-criteria)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Dependencies](#11-dependencies)
12. [Risks and Mitigations](#12-risks-and-mitigations)
13. [Open Questions](#13-open-questions)
14. [Implementation Plan](#14-implementation-plan)

---

## 1. Overview

### 1.1 Feature Summary

This PRD defines the requirements for implementing **Centralized Package Version Constraints** using uv's `constraint-dependencies` feature. The feature consolidates all external dependency version constraints into the root `pyproject.toml` file, while individual package `pyproject.toml` files specify only package names without version constraints.

### 1.2 Business Justification

- **Consistency:** Ensures all 13 packages in the monorepo use identical versions of shared dependencies, eliminating version drift and incompatibility issues.
- **Maintainability:** Provides a single location to update dependency versions, reducing the effort required to upgrade dependencies across the workspace.
- **Reduced Merge Conflicts:** Dependency version changes are isolated to the root `pyproject.toml`, minimizing conflicts when multiple developers update dependencies.
- **Compliance:** Enables easier security audits by providing a single manifest of all dependency versions.
- **Build Reproducibility:** Ensures consistent builds across development, CI, and production environments.

### 1.3 Background

The Microsoft Agent 365 SDK for Python is a monorepo containing 13 interdependent packages organized under `libraries/`. Currently, each package independently defines its dependency version constraints in its own `pyproject.toml` file. This leads to several challenges:

**Current State Analysis:**

| Dependency | Packages Using It | Version Constraint Variations |
|------------|-------------------|-------------------------------|
| `opentelemetry-api` | 6 packages | All use `>= 1.36.0` |
| `opentelemetry-sdk` | 5 packages | All use `>= 1.36.0` |
| `opentelemetry-instrumentation` | 4 packages | All use `>= 0.47b0` |
| `pydantic` | 4 packages | All use `>= 2.0.0` |
| `typing-extensions` | 4 packages | All use `>= 4.0.0` |
| `azure-identity` | 3 packages | All use `>= 1.12.0` |
| `microsoft-agents-hosting-core` | 4 packages | `>= 0.4.0` |
| `semantic-kernel` | 2 packages | All use `>= 1.0.0` |
| `langchain` | 1 package | `>= 0.1.0` |
| `langchain-core` | 1 package | `>= 0.1.0` |
| `aiohttp` | 1 package | `>= 3.8.0` |
| `PyJWT` | 1 package | `>= 2.8.0` |

While version constraints are currently consistent, maintaining this consistency becomes increasingly difficult as the monorepo grows. The proposed solution uses uv's native `constraint-dependencies` feature to enforce version consistency at the workspace level.

### 1.4 uv constraint-dependencies Feature

The `constraint-dependencies` feature in uv allows specifying version constraints that apply to all workspace members without adding those packages as direct dependencies. This is distinct from:

- **dependencies**: Packages that are installed
- **dev-dependencies**: Packages installed only during development
- **constraint-dependencies**: Version constraints that apply when a package is installed by any workspace member

When a workspace member declares a dependency (e.g., `opentelemetry-api`), uv applies the constraint from `constraint-dependencies` (e.g., `>= 1.36.0`) during resolution.

---

## 2. Objectives

### 2.1 Primary Objectives

| ID | Objective | Success Metric |
|----|-----------|----------------|
| O1 | Consolidate all external dependency version constraints into root pyproject.toml | All constraints moved to single location |
| O2 | Remove version constraints from individual package pyproject.toml files | All package pyproject.toml files use package names only |
| O3 | Maintain backward compatibility with existing builds | CI passes; all tests pass |
| O4 | Document the new dependency management pattern | README and CLAUDE.md updated |
| O5 | Ensure internal packages require exact version matches when published | Published package A v1.2.3 requires package B == 1.2.3 |

### 2.2 Non-Goals

- This feature does NOT change the actual versions of dependencies being used
- This feature does NOT modify the uv workspace membership or structure
- This feature does NOT add new dependencies to the project

---

## 3. User Stories

### 3.1 Developer Persona: SDK Maintainer

**As a** SDK maintainer responsible for keeping dependencies up to date,
**I want to** update dependency versions in a single location,
**So that** all packages in the monorepo automatically use the updated versions without requiring changes to multiple files.

**Acceptance Criteria:**
- I can update `opentelemetry-api` from `>= 1.36.0` to `>= 1.40.0` in one file
- Running `uv lock` applies the new constraint to all packages
- I don't need to modify any files in `libraries/*/pyproject.toml`

### 3.2 Developer Persona: New Package Developer

**As a** developer adding a new package to the monorepo,
**I want to** declare dependencies without specifying version constraints,
**So that** my package automatically uses the workspace-standard versions.

**Acceptance Criteria:**
- I can add `pydantic` to my package's dependencies without a version constraint
- The package uses the version constraint defined in root pyproject.toml
- Documentation explains this pattern clearly

### 3.3 Developer Persona: Security Engineer

**As a** security engineer auditing the SDK dependencies,
**I want to** review all external dependency versions in one location,
**So that** I can efficiently identify outdated or vulnerable packages.

**Acceptance Criteria:**
- All external dependency version constraints are listed in root pyproject.toml
- The constraint list is organized and documented
- I can identify which constraint applies to which dependency

### 3.4 Developer Persona: CI/CD Engineer

**As a** CI/CD engineer maintaining the build pipeline,
**I want to** ensure consistent dependency resolution across all environments,
**So that** builds are reproducible and predictable.

**Acceptance Criteria:**
- `uv lock` produces consistent results regardless of which package triggered the lock
- The lock file reflects the centralized constraints
- No changes to CI workflow files are required

---

## 4. Functional Requirements

### 4.1 Root pyproject.toml Changes

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Add `constraint-dependencies` property under `[tool.uv]` section | P0 |
| FR2 | List all external packages with their version constraints in `constraint-dependencies` | P0 |
| FR3 | Organize constraints alphabetically for maintainability | P1 |
| FR4 | Add comments categorizing constraints by package group (observability, Azure, frameworks) | P2 |
| FR5 | Preserve existing `dev-dependencies` without modification | P0 |

### 4.2 Package pyproject.toml Changes

| ID | Requirement | Priority |
|----|-------------|----------|
| FR6 | Remove version constraints from `dependencies` arrays in all 13 packages | P0 |
| FR7 | Retain package names only (e.g., change `pydantic >= 2.0.0` to `pydantic`) | P0 |
| FR8 | Remove version constraints from `optional-dependencies` (dev, test, azure, jaeger) | P0 |
| FR9 | Remove version placeholders from internal workspace dependencies (e.g., `microsoft-agents-a365-runtime >= 0.0.0` → `microsoft-agents-a365-runtime`) | P0 |
| FR10 | Preserve build-system requirements without modification | P0 |
| FR11 | Add all internal packages to `[tool.uv.sources]` with `{ workspace = true }` in root pyproject.toml | P0 |
| FR12 | Update all package `setup.py` files to use `use_exact_match=True` for internal dependencies | P0 |

### 4.3 Dependency Categories

The `constraint-dependencies` should include constraints for all external packages currently used across the workspace:

**Observability Dependencies:**
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-exporter-otlp-proto-grpc`
- `opentelemetry-instrumentation`

**Azure Dependencies:**
- `azure-identity`
- `azure-monitor-opentelemetry-exporter`
- `azure-monitor-ingestion`
- `azure-ai-projects`
- `azure-ai-agents`

**AI Framework Dependencies:**
- `openai-agents`
- `semantic-kernel`
- `langchain`
- `langchain-core`
- `agent-framework-azure-ai`
- `microsoft-agents-hosting-core`
- `microsoft-agents-activity`

**Utility Dependencies:**
- `pydantic`
- `typing-extensions`
- `aiohttp`
- `asyncio-throttle`
- `PyJWT`

**Development Dependencies:**
- `pytest`
- `pytest-asyncio`
- `pytest-mock`
- `ruff`
- `black`
- `mypy`
- `python-dotenv`
- `openai`

---

## 5. Technical Requirements

### 5.1 Architecture

The feature leverages uv's native constraint resolution mechanism:

```
                    +---------------------------+
                    |    Root pyproject.toml    |
                    |  +---------------------+  |
                    |  | [tool.uv]           |  |
                    |  | constraint-         |  |
                    |  |   dependencies = [  |  |
                    |  |   "pydantic>=2.0",  |  |
                    |  |   "otel-api>=1.36", |  |
                    |  |   ...               |  |
                    |  | ]                   |  |
                    |  +---------------------+  |
                    +------------+--------------+
                                 |
                                 | Constraints applied
                                 | during resolution
                                 v
       +-------------------------+-------------------------+
       |                         |                         |
       v                         v                         v
+-------------+          +-------------+          +-------------+
| Package A   |          | Package B   |          | Package C   |
| pyproject   |          | pyproject   |          | pyproject   |
| .toml       |          | .toml       |          | .toml       |
| deps: [     |          | deps: [     |          | deps: [     |
|  "pydantic",|          |  "pydantic",|          |  "otel-api",|
|  "otel-api" |          |  "aiohttp"  |          |  "otel-sdk" |
| ]           |          | ]           |          | ]           |
+-------------+          +-------------+          +-------------+
       |                         |                         |
       +-------------------------+-------------------------+
                                 |
                                 v
                    +---------------------------+
                    |       uv.lock             |
                    |  Resolved versions:       |
                    |  - pydantic==2.10.4       |
                    |  - otel-api==1.36.0       |
                    |  - aiohttp==3.11.11       |
                    |  - otel-sdk==1.36.0       |
                    +---------------------------+
```

### 5.2 Resolution Behavior

When uv resolves dependencies:

1. **Package declares dependency**: `dependencies = ["pydantic"]`
2. **uv finds constraint**: `constraint-dependencies = ["pydantic >= 2.0.0"]`
3. **uv resolves**: Finds version satisfying `>= 2.0.0`
4. **Lock file updated**: Records resolved version (e.g., `2.10.4`)

**Important Behaviors:**
- Constraints only apply when a package is actually depended upon
- Constraints do not add packages as dependencies
- Multiple constraints for the same package are combined (intersection)
- Constraints apply to all workspace members uniformly

### 5.3 Internal Dependency Handling

Internal workspace dependencies use a two-part system:

**1. Development Time (uv sources):**

All internal packages are listed in `[tool.uv.sources]` with `{ workspace = true }`. This tells uv to use the local workspace package during development instead of fetching from PyPI.

```toml
# In root pyproject.toml
[tool.uv.sources]
microsoft-agents-a365-runtime = { workspace = true }
microsoft-agents-a365-observability-core = { workspace = true }
microsoft-agents-a365-tooling = { workspace = true }
# ... all internal packages
```

**2. Build/Publish Time (setup.py):**

Each package's `setup.py` uses `get_dynamic_dependencies()` from `versioning/helper/setup_utils.py` to dynamically inject version constraints at build time. By setting `use_exact_match=True`, published packages will require exact version matches:

```python
# In each package's setup.py
setup(
    version=package_version,
    install_requires=get_dynamic_dependencies(
        use_exact_match=True,  # Package A v1.2.3 requires Package B == 1.2.3
    ),
)
```

**Package pyproject.toml files:**

Internal dependencies are listed by name only (no version constraint):

```toml
# In package pyproject.toml
dependencies = [
    "microsoft-agents-a365-runtime",  # No version - resolved by uv.sources during dev
    "microsoft-agents-a365-tooling",  # Version injected at build time by setup.py
]
```

**Benefits of this approach:**
- **Development**: Uses local workspace packages via `{ workspace = true }`
- **Published packages**: Require exact version matches (e.g., `== 1.2.3`), ensuring all SDK packages are in sync
- **Cleaner pyproject.toml**: No placeholder versions like `>= 0.0.0`

### 5.4 Build System Requirements

The `[build-system]` requires section uses different resolution and should remain unchanged:

```toml
# DO NOT MODIFY
[build-system]
requires = ["setuptools>=68", "wheel", "tzdata"]
build-backend = "setuptools.build_meta"
```

---

## 6. Package Impact Analysis

### 6.1 Modified Files

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` (root) | MODIFY | Add `constraint-dependencies` array; add all internal packages to `[tool.uv.sources]` |
| `libraries/microsoft-agents-a365-runtime/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-notifications/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-core/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-extensions-openai/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-extensions-langchain/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-extensions-semantickernel/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-extensions-agentframework/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-observability-hosting/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-tooling/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-tooling-extensions-openai/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-tooling-extensions-semantickernel/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-tooling-extensions-agentframework/pyproject.toml` | MODIFY | Remove version constraints |
| `libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/pyproject.toml` | MODIFY | Remove version constraints |
| `uv.lock` | REGENERATE | Regenerated by `uv lock` |
| `CLAUDE.md` | MODIFY | Document centralized version management |
| `scripts/verify_constraints.py` | NEW | Verification script to prevent version constraint regression |
| `.github/workflows/ci.yml` | MODIFY | Add verification script step |
| `libraries/*/setup.py` (13 files) | MODIFY | Change `use_exact_match=False` to `use_exact_match=True` |

### 6.2 Unchanged Components

| Component | Reason |
|-----------|--------|
| Source code (*.py files) | No code changes required |
| Test files | No test changes required |
| CI/CD workflows | No workflow changes required |
| Documentation (other than CLAUDE.md) | Optional enhancement |

### 6.3 Version Impact

This change does NOT require a version bump for any packages because:
- No functional changes to package code
- No changes to public APIs
- No changes to package metadata visible to consumers
- Lock file changes are normal operations

---

## 7. Configuration Design

### 7.1 Root pyproject.toml Structure

```toml
[tool.uv]
# Development dependencies for the entire workspace
dev-dependencies = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "ruff>=0.1.0",
    "python-dotenv>=1.0.0",
    "openai>=1.0.0",
    "agent-framework-azure-ai >= 1.0.0b251114",
    "azure-identity>=1.12.0",
    "openai-agents >= 0.2.6",
]

# Centralized version constraints for all workspace packages
# These constraints apply when a dependency is declared in any package's pyproject.toml
constraint-dependencies = [
    # --- Observability (OpenTelemetry) ---
    "opentelemetry-api >= 1.36.0",
    "opentelemetry-sdk >= 1.36.0",
    "opentelemetry-exporter-otlp >= 1.36.0",
    "opentelemetry-exporter-otlp-proto-grpc >= 1.36.0",
    "opentelemetry-instrumentation >= 0.47b0",

    # --- Azure Services ---
    "azure-identity >= 1.12.0",
    "azure-monitor-opentelemetry-exporter >= 1.0.0b39",
    "azure-monitor-ingestion >= 1.0.0",
    "azure-ai-projects >= 2.0.0b1",
    "azure-ai-agents >= 1.0.0b251001",

    # --- AI Frameworks ---
    "openai-agents >= 0.2.6",
    "semantic-kernel >= 1.0.0",
    "langchain >= 0.1.0",
    "langchain-core >= 0.1.0",
    "agent-framework-azure-ai >= 1.0.0b251114",

    # --- Microsoft Agents SDK ---
    "microsoft-agents-hosting-core >= 0.4.0",
    "microsoft-agents-activity >= 0.4.0",

    # --- Data Validation & Utilities ---
    "pydantic >= 2.0.0",
    "typing-extensions >= 4.0.0",
    "aiohttp >= 3.8.0",
    "asyncio-throttle >= 1.0.0",
    "PyJWT >= 2.8.0",

    # --- Development & Testing ---
    "pytest >= 7.0.0",
    "pytest-asyncio >= 0.21.0",
    "pytest-mock >= 3.10.0",
    "ruff >= 0.1.0",
    "black >= 23.0.0",
    "mypy >= 1.0.0",
    "python-dotenv >= 1.0.0",
    "openai >= 1.0.0",
]
```

### 7.2 Package pyproject.toml Example (Before/After)

**Before (microsoft-agents-a365-observability-core/pyproject.toml):**
```toml
dependencies = [
    "opentelemetry-api >= 1.36.0",
    "opentelemetry-sdk >= 1.36.0",
    "opentelemetry-exporter-otlp >= 1.36.0",
    "pydantic >= 2.0.0",
    "typing-extensions >= 4.0.0",
    "microsoft-agents-a365-runtime >= 0.0.0"
]

[project.optional-dependencies]
azure = [
    "azure-monitor-opentelemetry-exporter >= 1.0.0b39",
    "azure-identity >= 1.12.0",
    "azure-monitor-ingestion >= 1.0.0",
]
jaeger = [
    "opentelemetry-exporter-otlp-proto-grpc >= 1.36.0",
]
dev = [
    "pytest >= 7.0.0",
    "pytest-asyncio >= 0.21.0",
    "ruff >= 0.1.0",
    "black >= 23.0.0",
    "mypy >= 1.0.0",
]
test = [
    "pytest >= 7.0.0",
    "pytest-asyncio >= 0.21.0",
]
```

**After:**
```toml
dependencies = [
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp",
    "pydantic",
    "typing-extensions",
    "microsoft-agents-a365-runtime",  # Internal dep - no version (resolved via uv.sources)
]

[project.optional-dependencies]
azure = [
    "azure-monitor-opentelemetry-exporter",
    "azure-identity",
    "azure-monitor-ingestion",
]
jaeger = [
    "opentelemetry-exporter-otlp-proto-grpc",
]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
    "black",
    "mypy",
]
test = [
    "pytest",
    "pytest-asyncio",
]
```

### 7.3 CLAUDE.md Documentation Update

Add the following section to CLAUDE.md under "Architecture":

```markdown
### Centralized Dependency Version Management

This monorepo uses uv's `constraint-dependencies` feature to centralize version constraints:

**How it works:**
1. **Root pyproject.toml** defines version constraints for all external packages in `constraint-dependencies`
2. **Package pyproject.toml** files declare dependencies by name only (no version)
3. **uv** applies root constraints during dependency resolution

**Adding a new external dependency:**
1. Add the package name to your package's `dependencies` array (no version)
2. Add the version constraint to root `pyproject.toml` `constraint-dependencies`
3. Run `uv lock && uv sync`

**Updating an external dependency version:**
1. Edit the constraint in root `pyproject.toml` only
2. Run `uv lock && uv sync`
3. All packages automatically use the new version

**Internal workspace dependencies:**
- Package pyproject.toml files list internal deps by name only (e.g., `microsoft-agents-a365-runtime`)
- Root pyproject.toml `[tool.uv.sources]` maps them to `{ workspace = true }` for local development
- At build time, `setup.py` injects exact version matches (e.g., `== 1.2.3`) for published packages
- This ensures all SDK packages require the exact same version of each other
```

---

## 8. Testing Strategy

### 8.1 Validation Tests

| Test | Method | Success Criteria |
|------|--------|------------------|
| Lock file generates successfully | `uv lock` | Exit code 0; lock file created |
| Sync installs all dependencies | `uv sync --all-extras --dev` | Exit code 0; all packages installed |
| Unit tests pass | `pytest tests/ -m "not integration"` | All tests pass |
| Lint checks pass | `ruff check .` | No errors |
| Format checks pass | `ruff format --check .` | No differences |
| Build succeeds | `uv build --all-packages --wheel` | All 13 wheels built |

### 8.2 Constraint Verification Script

Create a verification script (`scripts/verify_constraints.py`) that enforces the centralized version management pattern:

**Script Requirements:**

1. **Parse root `pyproject.toml`** - Extract all packages listed in `constraint-dependencies`
2. **Parse all package `pyproject.toml` files** - Extract dependencies from:
   - `[project].dependencies`
   - `[project.optional-dependencies].*` (dev, test, azure, jaeger, etc.)
3. **Verify no version constraints in packages** - Check that external dependencies have no version specifiers (except internal `microsoft-agents-a365-*` packages)
4. **Verify constraint coverage** - Ensure all external packages used in any package have a constraint defined in root
5. **Report violations** - Output clear error messages with file paths and line numbers

**Script Output:**

```
Checking centralized version constraints...

Scanning 13 package pyproject.toml files...
  - libraries/microsoft-agents-a365-runtime/pyproject.toml: OK
  - libraries/microsoft-agents-a365-notifications/pyproject.toml: OK
  ...

Verifying constraint coverage...
  - All 32 external dependencies have constraints defined

Result: PASSED
```

**Error Example:**

```
ERROR: Version constraint found in package file
  File: libraries/microsoft-agents-a365-runtime/pyproject.toml
  Line 28: "pydantic >= 2.0.0"
  Expected: "pydantic" (version constraint should be in root pyproject.toml)

Result: FAILED (1 violation)
```

**CI Integration:**

Add the script to `.github/workflows/ci.yml` as an early step (before lint/test):

```yaml
- name: Verify centralized version constraints
  run: python scripts/verify_constraints.py
```

### 8.3 Regression Tests

| Test | Method | Success Criteria |
|------|--------|------------------|
| Integration tests pass | `pytest -m integration` | All tests pass (when secrets available) |
| Installed versions match expectations | `uv pip list` | Versions satisfy constraints |
| No version conflicts | `uv lock` | No resolution errors |

---

## 9. Acceptance Criteria

### 9.1 Functional Acceptance

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC1 | Root pyproject.toml contains `constraint-dependencies` with all external packages | Manual review |
| AC2 | All 13 package pyproject.toml files have no version constraints on external deps | Script verification |
| AC3 | Internal workspace dependencies retain version placeholders | Manual review |
| AC4 | `uv lock` completes successfully | CI pipeline |
| AC5 | `uv sync --all-extras --dev` completes successfully | CI pipeline |
| AC6 | All unit tests pass | CI pipeline |
| AC7 | All lint checks pass | CI pipeline |
| AC8 | All packages build successfully | CI pipeline |

### 9.2 Documentation Acceptance

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC9 | CLAUDE.md updated with centralized version management documentation | Manual review |
| AC10 | Comments in root pyproject.toml explain constraint categories | Manual review |

### 9.3 Verification Script Acceptance

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC11 | `scripts/verify_constraints.py` exists and is executable | File exists |
| AC12 | Script detects version constraints in package files | Unit test |
| AC13 | Script detects missing constraints in root | Unit test |
| AC14 | Script integrated into CI workflow | CI pipeline runs script |
| AC15 | Script passes on the migrated codebase | CI pipeline |

### 9.4 Non-Regression Acceptance

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC16 | No changes to resolved dependency versions | Compare lock file before/after |
| AC17 | No source code changes required (except new script) | Git diff |

---

## 10. Non-Functional Requirements

### 10.1 Maintainability

| Requirement | Target |
|-------------|--------|
| Single location for version updates | Root pyproject.toml only |
| Clear categorization of constraints | Comments for each category |
| Alphabetical ordering within categories | Enforced |

### 10.2 Compatibility

| Requirement | Target |
|-------------|--------|
| uv version | >= 0.4.0 (constraint-dependencies support) |
| Python versions | 3.11, 3.12 (unchanged) |
| Backward compatibility | Existing workflows unchanged |

### 10.3 Performance

| Requirement | Target |
|-------------|--------|
| Lock time | No significant increase |
| Sync time | No significant increase |
| Build time | No change |

---

## 11. Dependencies

### 11.1 External Tool Dependencies

| Tool | Version | Purpose |
|------|---------|---------|
| uv | >= 0.4.0 | Package manager with constraint-dependencies support |

### 11.2 Process Dependencies

| Dependency | Reason |
|------------|--------|
| CI pipeline access | Verify all tests pass |
| Branch protection rules | Require PR review |

---

## 12. Risks and Mitigations

### 12.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| uv constraint-dependencies behaves unexpectedly | High | Low | Test thoroughly in feature branch; review uv documentation |
| Constraint conflicts during resolution | Medium | Low | Verify all current constraints are compatible; use `uv lock --verbose` |
| Missing constraint for a package | Medium | Medium | Create verification script to check all deps have constraints |
| Version drift during transition | Low | Low | Compare lock files before and after changes |

### 12.2 Process Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Incomplete migration of constraints | Medium | Low | Use checklist and verification script |
| Developer confusion about new pattern | Medium | Medium | Update CLAUDE.md; communicate change in PR |
| Accidental reintroduction of version constraints | Low | Medium | Add verification to CI pipeline |

### 12.3 Rollback Plan

If issues are discovered after merge:

1. Revert the PR (all changes in single commit)
2. Run `uv lock` to regenerate lock file
3. Verify CI passes

---

## 13. Open Questions

### 13.1 Resolved Questions

| ID | Question | Resolution |
|----|----------|------------|
| Q1 | Should dev-dependencies in package pyproject.toml files also have version constraints removed? | **Yes** - All dev dependencies defined in individual package `pyproject.toml` files should have version constraints removed. The constraints will be centralized in root `pyproject.toml` `constraint-dependencies`. |
| Q2 | How to handle build-system requires? | Leave unchanged - different resolution mechanism |
| Q3 | Should internal deps use constraints? | No - they use workspace=true and build-time version replacement |
| Q4 | Should we add a CI check to prevent version constraints in package files? | **Yes** - Create a verification script and integrate it into CI to prevent regression |
| Q5 | Should the verification script be added to CI? | **Yes** - The verification script provides value by preventing accidental reintroduction of version constraints |

### 13.2 Open Questions

None - all questions have been resolved.

---

## 14. Implementation Plan

### 14.1 Implementation Steps

See the detailed task breakdown document: [CentralizedPackageVersions-Tasks.md](./tasks/CentralizedPackageVersions-Tasks.md)

**Summary of phases:**

| Phase | Description | Tasks |
|-------|-------------|-------|
| 1 | Setup and Root Configuration | Create branch, add constraint-dependencies |
| 2 | Core Package Migration | Update runtime, notifications, observability-core, tooling |
| 3 | Observability Extensions Migration | Update 4 observability extension packages |
| 4 | Tooling Extensions Migration | Update 4 tooling extension packages |
| 5 | Verification Script | Create and test verify_constraints.py |
| 6 | CI Integration | Add verification to CI workflow |
| 7 | Documentation | Update CLAUDE.md |
| 8 | Validation and Finalization | Run tests, create PR, merge |

### 14.2 Complete Constraint List

Based on analysis of all 13 packages, the complete `constraint-dependencies` list:

```toml
constraint-dependencies = [
    # --- Observability (OpenTelemetry) ---
    "opentelemetry-api >= 1.36.0",
    "opentelemetry-sdk >= 1.36.0",
    "opentelemetry-exporter-otlp >= 1.36.0",
    "opentelemetry-exporter-otlp-proto-grpc >= 1.36.0",
    "opentelemetry-instrumentation >= 0.47b0",

    # --- Azure Services ---
    "azure-ai-agents >= 1.0.0b251001",
    "azure-ai-projects >= 2.0.0b1",
    "azure-identity >= 1.12.0",
    "azure-monitor-ingestion >= 1.0.0",
    "azure-monitor-opentelemetry-exporter >= 1.0.0b39",

    # --- AI Frameworks ---
    "agent-framework-azure-ai >= 1.0.0b251114",
    "langchain >= 0.1.0",
    "langchain-core >= 0.1.0",
    "openai-agents >= 0.2.6",
    "semantic-kernel >= 1.0.0",

    # --- Microsoft Agents SDK ---
    "microsoft-agents-activity >= 0.4.0",
    "microsoft-agents-hosting-core >= 0.4.0",

    # --- Data Validation & Utilities ---
    "aiohttp >= 3.8.0",
    "asyncio-throttle >= 1.0.0",
    "pydantic >= 2.0.0",
    "PyJWT >= 2.8.0",
    "typing-extensions >= 4.0.0",

    # --- Development & Testing ---
    "black >= 23.0.0",
    "mypy >= 1.0.0",
    "openai >= 1.0.0",
    "pytest >= 7.0.0",
    "pytest-asyncio >= 0.21.0",
    "pytest-mock >= 3.10.0",
    "python-dotenv >= 1.0.0",
    "ruff >= 0.1.0",
]
```

---

## Appendix A: Package Dependency Matrix

| Package | External Dependencies (to migrate) |
|---------|-----------------------------------|
| runtime | PyJWT |
| notifications | typing-extensions, pydantic, microsoft-agents-activity, microsoft-agents-hosting-core |
| observability-core | opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp, pydantic, typing-extensions |
| observability-core [azure] | azure-monitor-opentelemetry-exporter, azure-identity, azure-monitor-ingestion |
| observability-core [jaeger] | opentelemetry-exporter-otlp-proto-grpc |
| observability-extensions-openai | openai-agents, opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation |
| observability-extensions-langchain | langchain, langchain-core, opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation |
| observability-extensions-semantickernel | semantic-kernel, opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation |
| observability-extensions-agentframework | opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation |
| observability-hosting | opentelemetry-api, microsoft-agents-hosting-core |
| tooling | pydantic, typing-extensions, microsoft-agents-hosting-core |
| tooling-extensions-openai | openai-agents, asyncio-throttle |
| tooling-extensions-semantickernel | semantic-kernel, aiohttp |
| tooling-extensions-agentframework | microsoft-agents-hosting-core, agent-framework-azure-ai, azure-identity, typing-extensions |
| tooling-extensions-azureaifoundry | azure-ai-projects, azure-ai-agents, azure-identity |
| ALL [dev] | pytest, pytest-asyncio, ruff, black, mypy |
| ALL [test] | pytest, pytest-asyncio |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| constraint-dependencies | uv feature that specifies version constraints applied during resolution |
| Workspace | uv concept grouping related packages that are developed together |
| Lock file | File (uv.lock) recording exact resolved versions of all dependencies |
| Internal dependency | A package within the same workspace (uses workspace=true) |
| External dependency | A package from PyPI or other external source |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-27 | Engineering Team | Initial draft |
| 1.1 | 2026-01-27 | Engineering Team | Resolved all open questions; added verification script requirements and CI integration; created task breakdown document |
| 1.2 | 2026-01-27 | Engineering Team | Added internal dependency version synchronization: remove `>= 0.0.0` placeholders, add all packages to `[tool.uv.sources]`, update setup.py to use exact version matching |

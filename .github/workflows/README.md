# GitHub Actions Workflows

This directory contains GitHub Actions workflows for the Microsoft Agent 365 SDK for Python repository.

## CI Workflow (ci.yml)

The main CI workflow builds, tests, and prepares SDK packages for publishing:

### Jobs

#### Python SDK (`python-sdk`)
- **Matrix**: Python 3.11 and 3.12
- **Steps**:
  - Install dependencies and build tools
  - Optional linting with ruff
  - Build Python package using `python -m build`
  - Run tests with pytest

### Triggers

- **Push**: Triggers on pushes to `main` or `master` branches
- **Pull Request**: Triggers on pull requests targeting `main` or `master` branches

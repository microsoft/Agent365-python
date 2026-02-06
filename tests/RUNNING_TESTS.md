# Running Unit Tests for Agent365-Python SDK

This guide covers setting up and running tests.

---

## Prerequisites

### 1. Create Virtual Environment

```powershell
# Create virtual environment using uv
uv venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

### 2. Configure Python Environment

1. Press `Ctrl+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose the `.venv` interpreter from the list

### 3. Install Dependencies

```powershell
# Test framework and reporting
uv pip install pytest pytest-asyncio pytest-mock pytest-cov pytest-html wrapt

# SDK core libraries
uv pip install -e libraries/microsoft-agents-a365-runtime -e libraries/microsoft-agents-a365-notifications -e libraries/microsoft-agents-a365-observability-core -e libraries/microsoft-agents-a365-tooling

# Framework extension libraries
uv pip install -e libraries/microsoft-agents-a365-observability-extensions-langchain -e libraries/microsoft-agents-a365-observability-extensions-openai -e libraries/microsoft-agents-a365-observability-extensions-semantickernel -e libraries/microsoft-agents-a365-observability-extensions-agentframework -e libraries/microsoft-agents-a365-tooling-extensions-agentframework -e libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry -e libraries/microsoft-agents-a365-tooling-extensions-openai -e libraries/microsoft-agents-a365-tooling-extensions-semantickernel -e libraries/microsoft-agents-a365-tooling-extensions-googleadk
```

---

## Test Structure

> **Note:** This structure will be updated as new tests are added.

```plaintext
tests/
├── runtime/                           # Runtime tests
├── observability/                     # Observability tests
├── tooling/                           # Tooling tests
└── notifications/                     # Notifications tests
```

---

## Running Tests in VS Code (Optional)

### Test Explorer

1. Click the beaker icon in the Activity Bar or press `Ctrl+Shift+P` → "Test: Focus on Test Explorer View"
2. Click the play button to run tests (all/folder/file/individual)
3. Right-click → "Debug Test" to debug with breakpoints

### Command Palette

- `Test: Run All Tests`
- `Test: Run Tests in Current File`
- `Test: Debug Tests in Current File`

---

## Running Tests from Command Line

```powershell
# Run all tests
python -m pytest tests/

# Run specific module/file
python -m pytest tests/runtime/
python -m pytest tests/runtime/test_environment_utils.py

# Run with options
python -m pytest tests/ -v                    # Verbose
python -m pytest tests/ -x                    # Stop on first failure
python -m pytest tests/ -k "environment"      # Pattern matching
python -m pytest --lf                         # Re-run failed tests
```

---

## Generating Reports

### HTML Reports

```powershell
# Coverage report
python -m pytest tests/ --cov=libraries --cov-report=html -v

# View reports
start htmlcov\index.html

# Test report (requires: uv pip install pytest-html)
python -m pytest tests/ --html=test-report.html --self-contained-html

# View reports
start test-report.html

# Combined (requires: uv pip install pytest-html)
python -m pytest tests/ --cov=libraries --cov-report=html --html=test-report.html --self-contained-html -v

# View reports
start htmlcov\index.html
```

### CI/CD Reports

```powershell
# XML reports for CI/CD pipelines
python -m pytest tests/ --cov=libraries --cov-report=xml --junitxml=test-results.xml

# View reports
start test-results.xml
start coverage.xml
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Test loading failed** | Clean pyproject.toml, reinstall packages, restart VS Code |
| **ImportError: No module named 'pytest'** | `uv pip install pytest pytest-asyncio pytest-mock` |
| **ImportError: No module named 'microsoft_agents_a365'** | `uv pip install -e .` |
| **Tests not discovered** | Refresh Test Explorer or restart VS Code |

### Fix Steps

If tests fail to discover or import errors occur:

**1. Clean pyproject.toml**

```powershell
$content = Get-Content "pyproject.toml" -Raw
$fixed = $content -replace "`r`n", "`n"
$fixed | Set-Content "pyproject.toml" -NoNewline
```

**2. Reinstall packages**

```powershell
uv pip install -e .
```

**3. Restart VS Code**

- Close completely and reopen
- Wait for Python extension to reload
- Refresh Test Explorer

# Microsoft Agent 365 SDK for Python - Architecture and Design

This uv workspace contains **eight distributions** for Notifications, Runtime,
Tooling, and five framework-specific Tooling adapters. It extends the
[Microsoft 365 Agents SDK](https://github.com/microsoft/Agents-for-python) for
Microsoft 365, Teams, Copilot Studio, and Webchat applications.

**Observability is no longer implemented, built, or released here.** Use the
separately maintained [Microsoft OpenTelemetry Distro](https://github.com/microsoft/opentelemetry-distro-python)
and follow the [migration guide](observability-migration.md). Its APIs and
authentication are not drop-in substitutes for the retired SDK.

## Repository and package layout

```text
libraries/
  microsoft-agents-a365-notifications/
  microsoft-agents-a365-runtime/
  microsoft-agents-a365-tooling/
  microsoft-agents-a365-tooling-extensions-agentframework/
  microsoft-agents-a365-tooling-extensions-azureaifoundry/
  microsoft-agents-a365-tooling-extensions-googleadk/
  microsoft-agents-a365-tooling-extensions-openai/
  microsoft-agents-a365-tooling-extensions-semantickernel/
tests/
  runtime/
  tooling/
  test_*.py                 # Build, constraints, metadata, and release tests
scripts/                     # Constraint and release-artifact verification
versioning/helper/           # Shared build backend and version injection
docs/changelogs/             # Preserved retired-package changelogs
```

Each library has a `pyproject.toml`, `setup.py`, README, and source under the
shared `microsoft_agents_a365` namespace. Directory/distribution names use dashes;
Python imports use underscores. The root manifest is the authoritative workspace
inventory. See [the generated dependency diagrams](../DEPENDENCIES.md) for all
internal and direct external dependencies.

## Remaining core packages

| Distribution | Responsibilities | Detailed design |
|---|---|---|
| `microsoft-agents-a365-runtime` | JWT/agent identity utilities, environment detection, Power Platform endpoint discovery, operation results | [Runtime](../libraries/microsoft-agents-a365-runtime/docs/design.md) |
| `microsoft-agents-a365-notifications` | Notification models, activity routing, agent lifecycle events and handlers | [Notifications](../libraries/microsoft-agents-a365-notifications/docs/design.md) |
| `microsoft-agents-a365-tooling` | MCP server discovery/configuration, tool access and chat-history submission | [Tooling](../libraries/microsoft-agents-a365-tooling/docs/design.md) |

### Runtime

`Utility` handles token decoding, agent identity resolution, and user-agent
generation. `OperationResult` and `OperationError` represent operation success or
failure without requiring exceptions for expected failures.
`PowerPlatformApiDiscovery` resolves gateway and island endpoints for different
cloud/cluster environments. These generic utilities remain even where retired
observability code previously called them.

The observability-specific scope helper and constants are removed. Runtime does
not configure telemetry or select an authentication flow for the external distro.

### Notifications

Notification handlers and models remain independent of telemetry configuration.
`AgentNotification` and `AgentHandler` route and handle notification activities;
`AgentLifecycleEvent`, `EmailReference`, `AgentSubChannel`, and notification type
models supply typed metadata. Removing tracing must not remove lifecycle or
notification delivery behavior.

### Tooling and framework adapters

`McpToolServerConfigurationService` discovers MCP servers using a local
`ToolingManifest.json` in development or the authenticated gateway in production.
`MCPServerConfig` describes discovered tool-server configuration.

| Adapter distribution suffix | Integration | Detailed design |
|---|---|---|
| `tooling-extensions-agentframework` | Microsoft Agent Framework | [Agent Framework](../libraries/microsoft-agents-a365-tooling-extensions-agentframework/docs/design.md) |
| `tooling-extensions-azureaifoundry` | Azure AI Foundry | [Azure AI Foundry](../libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/docs/design.md) |
| `tooling-extensions-googleadk` | Google ADK | [Google ADK](../libraries/microsoft-agents-a365-tooling-extensions-googleadk/docs/design.md) |
| `tooling-extensions-openai` | OpenAI Agents | [OpenAI](../libraries/microsoft-agents-a365-tooling-extensions-openai/docs/design.md) |
| `tooling-extensions-semantickernel` | Semantic Kernel | [Semantic Kernel](../libraries/microsoft-agents-a365-tooling-extensions-semantickernel/docs/design.md) |

All distribution suffixes above are prefixed with `microsoft-agents-a365-`.
Adapters translate discovered MCP tools to their framework's supported APIs.
For example, the OpenAI `McpToolRegistrationService` exposes `send_chat_history`
for a framework session and `send_chat_history_messages` for explicit messages;
these convert framework messages to the core chat-history format and delegate to
the MCP platform. This real-time threat-protection path remains supported.
Chat-history submission is not an observability span exporter.

## Patterns and data flow

Core functionality remains framework-agnostic; adapters depend on core packages
and their respective external frameworks. They must not depend on a retired
observability distribution. Some retained frameworks themselves depend on
OpenTelemetry: those transitive dependencies do not restore the retired SDK.

Expected operation failures use `OperationResult`:

```python
result = await some_operation()
if result.succeeded:
    handle_success()
else:
    for error in result.errors:
        handle_error(error)
```

MCP discovery selects the development/production strategy:

```text
Application -> McpToolServerConfigurationService.list_tool_servers()
  development -> locate ToolingManifest.json -> parse -> MCPServerConfig list
  production  -> Runtime gateway discovery -> authenticated HTTP -> server list
Framework adapter -> register discovered tools -> framework tool execution
```

Chat-history flow remains separate:

```text
Framework session/messages -> adapter conversion -> core chat-history API
  -> authenticated MCP platform request -> OperationResult
```

Use explicit tenant/agent identity, existing authentication services, and async
I/O patterns. Preserve error reporting rather than silently skipping behavior.
See individual package design documents for detailed APIs and examples.

## Dependency and release management

The root `pyproject.toml` centralizes external version constraints.
Library manifests declare dependency names without local version constraints.
Root `[tool.uv.sources]` entries map internal dependencies to the workspace.
The shared build backend injects centralized constraints into published wheel
metadata and pins internal dependencies to the exact SDK build version.
Run `scripts/verify_constraints.py` after manifest changes.

CI checks constraints, lint, formatting, builds, and tests on Python 3.11/3.12.
Builds use fresh output directories. `scripts/verify_release_artifacts.py`
requires the exact active wheel set and build version, rejects retired payloads
and dependencies, and runs before publication. Do not copy or upload stale
`dist/*`, old drops, or outputs from historical checkouts.

Publishing is restricted to SDK-changing pushes on `release/*`. A downstream
job waits for both Python matrix jobs, downloads the Python 3.11 artifact, and
re-verifies those wheels before upload. Tags influence versioning but are
not themselves the workflow's publication trigger. External promotion pipelines,
old branch permissions, and PyPI project retirement require
[owner action](observability-migration.md#release-controls-and-external-actions).
See [versioning and safe builds](../HOW_TO_SET_A_VERSION.md).

## Development and verification

Use Python 3.11+ and uv. From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) "versioning/helper"
uv sync --locked --all-extras --dev
uv run --frozen python scripts/verify_constraints.py
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest tests -v --tb=short -m "not integration"
```

Runtime/Tooling tests and distribution metadata tests remain, including constraint
and artifact-retirement guards. Async tests use pytest-asyncio. All remaining
tests are offline/mocked; the removed observability suite contained the live
integration tests. See [test execution](../tests/RUNNING_TESTS.md).
Each library's manifest also carries its existing strict mypy configuration.

Set `AGENT365_PYTHON_SDK_PACKAGE_VERSION` before building. Use a fresh directory
and verify it before any promotion or upload:

```powershell
$env:AGENT365_PYTHON_SDK_PACKAGE_VERSION = "0.1.0"
$output = Join-Path ([System.IO.Path]::GetTempPath()) ("agent365-wheels-" + [guid]::NewGuid())
uv build --all-packages --wheel --out-dir $output
uv run --frozen --no-sync python scripts/verify_release_artifacts.py $output --version $env:AGENT365_PYTHON_SDK_PACKAGE_VERSION
```

All Python source needs Microsoft copyright headers, type annotations, explicit
`None` checks, and repository-standard error handling. Ruff uses a 100-character
line limit. See [repository instructions](../CLAUDE.md) for the full standards.

## Resources

- [Microsoft Agent 365 developer documentation](https://learn.microsoft.com/microsoft-agent-365/developer/)
- [Microsoft 365 Agents SDK documentation](https://learn.microsoft.com/microsoft-365/agents-sdk/)
- [Sample applications](https://github.com/microsoft/Agent365-Samples/tree/main/python)
- [Observability migration and retirement checklist](observability-migration.md)

# Microsoft Agent 365 SDK for Python - Architecture and Design

This document describes the architecture and design of the Microsoft Agent 365 SDK for Python. It is intended to help developers and coding agents understand the project structure and quickly get started reading, writing, and reviewing code.

## Overview

The Microsoft Agent 365 SDK extends the [Microsoft 365 Agents SDK](https://github.com/Microsoft/Agents-for-python) with enterprise-grade capabilities for building sophisticated AI agents. It provides comprehensive tooling for:

- **Observability**: OpenTelemetry-based tracing, monitoring, and context propagation
- **Notifications**: Agent notification services and activity routing
- **Runtime**: Core utilities for agent operations and Power Platform integration
- **Tooling**: MCP (Model Context Protocol) server configuration and tool discovery

The SDK supports production deployment across Microsoft 365, Teams, Copilot Studio, and Webchat platforms.

## Repository Structure

```
Agent365-python/
├── libraries/                              # Core packages (13 total)
│   ├── microsoft-agents-a365-notifications/
│   ├── microsoft-agents-a365-observability-core/
│   ├── microsoft-agents-a365-observability-extensions-agentframework/
│   ├── microsoft-agents-a365-observability-extensions-langchain/
│   ├── microsoft-agents-a365-observability-extensions-openai/
│   ├── microsoft-agents-a365-observability-extensions-semantickernel/
│   ├── microsoft-agents-a365-observability-hosting/
│   ├── microsoft-agents-a365-runtime/
│   ├── microsoft-agents-a365-tooling/
│   ├── microsoft-agents-a365-tooling-extensions-agentframework/
│   ├── microsoft-agents-a365-tooling-extensions-azureaifoundry/
│   ├── microsoft-agents-a365-tooling-extensions-openai/
│   └── microsoft-agents-a365-tooling-extensions-semantickernel/
├── tests/                                  # Test suite
│   ├── observability/
│   ├── runtime/
│   └── tooling/
├── docs/                                   # Documentation
├── versioning/                             # Version management
└── pyproject.toml                          # Workspace configuration
```

### Package Layout

Each package follows a consistent structure:

```
libraries/microsoft-agents-a365-<name>/
├── microsoft_agents_a365/
│   └── <module>/                           # Source code
│       ├── __init__.py                     # Public API exports
│       ├── models/                         # Data classes
│       ├── services/                       # Service implementations
│       └── utils/                          # Utilities
├── pyproject.toml                          # Package configuration
└── README.md                               # Package documentation
```

## Core Packages

> **Note**: Each package has its own detailed design document in `libraries/<package-name>/docs/design.md`. The sections below provide an overview; refer to the package-specific documents for implementation details.

### 1. Observability Core (`microsoft-agents-a365-observability-core`)

> **Detailed documentation**: [libraries/microsoft-agents-a365-observability-core/docs/design.md](../libraries/microsoft-agents-a365-observability-core/docs/design.md)

The foundation for distributed tracing in agent applications. Built on OpenTelemetry.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `configure()` | Initialize telemetry with service name, namespace, and exporter options |
| `InvokeAgentScope` | Trace agent invocation lifecycle (entry point for agent requests) |
| `InferenceScope` | Trace LLM/AI model inference calls |
| `ExecuteToolScope` | Trace tool execution operations |
| `BaggageBuilder` | Fluent API for context propagation across async boundaries |
| `SpanProcessor` | Copies baggage entries to span attributes |

**Data Classes:**

| Class | Purpose |
|-------|---------|
| `InvokeAgentDetails` | Agent endpoint, session ID, and invocation metadata |
| `AgentDetails` | Agent identification and metadata |
| `TenantDetails` | Tenant identification for multi-tenant scenarios |
| `InferenceCallDetails` | Model name, tokens, provider information |
| `ToolCallDetails` | Tool name, arguments, endpoint |
| `Request` | Execution context and correlation ID |

**Usage Example:**

```python
from microsoft_agents_a365.observability.core import (
    configure,
    InvokeAgentScope,
    InvokeAgentDetails,
    TenantDetails,
    Request,
    BaggageBuilder,
)

# Initialize telemetry
configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    token_resolver=lambda agent_id, tenant_id: get_auth_token(),
    cluster_category="prod"
)

# Set context for child spans
with BaggageBuilder().tenant_id(tenant_id).agent_id(agent_id).build():
    # Trace agent invocation
    with InvokeAgentScope.start(
        invoke_agent_details=InvokeAgentDetails(...),
        tenant_details=TenantDetails(...),
        request=Request(...)
    ) as scope:
        # Agent logic here
        scope.record_response("result")
```

### 2. Observability Extensions

Framework-specific instrumentations that integrate with the observability core:

| Package | Purpose | Design Doc |
|---------|---------|------------|
| `extensions-openai` | Instrument OpenAI SDK client calls | [design.md](../libraries/microsoft-agents-a365-observability-extensions-openai/docs/design.md) |
| `extensions-langchain` | LangChain callback integration | [design.md](../libraries/microsoft-agents-a365-observability-extensions-langchain/docs/design.md) |
| `extensions-agentframework` | Microsoft Agents SDK integration | [design.md](../libraries/microsoft-agents-a365-observability-extensions-agentframework/docs/design.md) |
| `extensions-semantickernel` | Semantic Kernel instrumentation | [design.md](../libraries/microsoft-agents-a365-observability-extensions-semantickernel/docs/design.md) |
| `hosting` | Hosting-specific observability utilities | — |

### 3. Runtime (`microsoft-agents-a365-runtime`)

> **Detailed documentation**: [libraries/microsoft-agents-a365-runtime/docs/design.md](../libraries/microsoft-agents-a365-runtime/docs/design.md)

Core utilities shared across the SDK.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `Utility` | Token decoding, agent identity resolution, user-agent generation |
| `OperationResult` | Standardized success/failure result pattern (no exceptions) |
| `OperationError` | Error details for failed operations |
| `PowerPlatformApiDiscovery` | Endpoint discovery for different cloud environments |
| `ClusterCategory` | Enum for cluster environments (prod, ppe, test, etc.) |

**Usage Example:**

```python
from microsoft_agents_a365.runtime import (
    Utility,
    OperationResult,
    PowerPlatformApiDiscovery,
    ClusterCategory,
)

# Decode agent identity from JWT token
app_id = Utility.get_app_id_from_token(jwt_token)

# Discover Power Platform endpoints
discovery = PowerPlatformApiDiscovery()
endpoint = discovery.get_tenant_island_cluster_endpoint(
    tenant_id=tenant_id,
    cluster_category=ClusterCategory.PROD
)

# Handle operation results
result = some_operation()
if result.succeeded:
    process_success()
else:
    for error in result.errors:
        log_error(error)
```

### 4. Tooling (`microsoft-agents-a365-tooling`)

> **Detailed documentation**: [libraries/microsoft-agents-a365-tooling/docs/design.md](../libraries/microsoft-agents-a365-tooling/docs/design.md)

MCP (Model Context Protocol) tool server configuration and discovery.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `McpToolServerConfigurationService` | Discover and configure MCP tool servers |
| `MCPServerConfig` | Tool server configuration (name, endpoint URL) |
| `Constants` | Configuration constants |

**Dual-Mode Configuration:**

The tooling package supports two modes based on the `ENVIRONMENT` variable:

- **Development** (`ENVIRONMENT=Development`): Loads tool servers from a local `ToolingManifest.json` file
- **Production** (default): Discovers tool servers from the Agent365 gateway endpoint

**Usage Example:**

```python
from microsoft_agents_a365.tooling import (
    McpToolServerConfigurationService,
    MCPServerConfig,
)

service = McpToolServerConfigurationService()

# Discover available tool servers
servers = await service.list_tool_servers(
    agentic_app_id=app_id,
    auth_token=bearer_token
)

for server in servers:
    print(f"Tool: {server.mcp_server_name}")
    print(f"Endpoint: {server.mcp_server_unique_name}")
```

### 5. Tooling Extensions

Framework-specific adapters for MCP tool integration:

| Package | Purpose | Design Doc |
|---------|---------|------------|
| `extensions-agentframework` | Adapt MCP tools to Microsoft Agents SDK | [design.md](../libraries/microsoft-agents-a365-tooling-extensions-agentframework/docs/design.md) |
| `extensions-azureaifoundry` | Azure AI Foundry tool integration | [design.md](../libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry/docs/design.md) |
| `extensions-openai` | OpenAI function calling integration and chat history | [design.md](../libraries/microsoft-agents-a365-tooling-extensions-openai/docs/design.md) |
| `extensions-semantickernel` | Semantic Kernel plugin integration | [design.md](../libraries/microsoft-agents-a365-tooling-extensions-semantickernel/docs/design.md) |

#### OpenAI Extension: Chat History API

The OpenAI tooling extension provides methods to send chat history to the MCP platform for real-time threat protection:

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `McpToolRegistrationService` | MCP tool registration and chat history management |

**Methods:**

| Method | Purpose |
|--------|---------|
| `send_chat_history(turn_context, session, limit, options)` | Extract messages from OpenAI Session and send to MCP platform |
| `send_chat_history_messages(turn_context, messages, options)` | Send a list of OpenAI TResponseInputItem messages to MCP platform |

**Usage Example:**

```python
from agents import Agent, Runner
from microsoft_agents_a365.tooling.extensions.openai import McpToolRegistrationService

service = McpToolRegistrationService()
agent = Agent(name="my-agent", model="gpt-4")

# In your agent handler:
async with Runner.run(agent, messages) as result:
    session = result.session

    # Option 1: Send from Session object
    op_result = await service.send_chat_history(turn_context, session)

    # Option 2: Send from message list
    op_result = await service.send_chat_history_messages(turn_context, messages)

    if op_result.succeeded:
        print("Chat history sent successfully")
```

The methods convert OpenAI message types to `ChatHistoryMessage` format and delegate to the core `McpToolServerConfigurationService.send_chat_history()` method.

### 6. Notifications (`microsoft-agents-a365-notifications`)

> **Detailed documentation**: [libraries/microsoft-agents-a365-notifications/docs/design.md](../libraries/microsoft-agents-a365-notifications/docs/design.md)

Agent notification and lifecycle event handling.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `AgentNotification` | Main notification handler |
| `AgentHandler` | Base class for notification handlers |
| `AgentNotificationActivity` | Notification activity data |
| `AgentLifecycleEvent` | Agent lifecycle events (start, stop, etc.) |
| `EmailReference` | Email notification metadata |
| `AgentSubChannel` | Sub-channel routing information |
| `NotificationTypes` | Enum of notification types |

## Design Patterns

### 1. Singleton Pattern

`TelemetryManager` uses thread-safe singleton with double-checked locking to ensure a single tracer provider per application:

```python
# Internal implementation pattern
class TelemetryManager:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
```

### 2. Context Manager Pattern

All scope classes implement `__enter__` and `__exit__` for automatic span lifecycle management:

```python
with InvokeAgentScope.start(...) as scope:
    # Span is active
    scope.record_response("result")
# Span automatically ends, errors recorded if exception raised
```

### 3. Builder Pattern

`BaggageBuilder` provides a fluent API for context propagation:

```python
with BaggageBuilder() \
    .tenant_id(tenant_id) \
    .agent_id(agent_id) \
    .correlation_id(correlation_id) \
    .build():
    # Baggage propagated to child spans
```

### 4. Result Pattern

`OperationResult` encapsulates success/failure without exceptions:

```python
result = await some_operation()
if result.succeeded:
    handle_success()
else:
    for error in result.errors:
        handle_error(error)
```

### 5. Strategy Pattern

`McpToolServerConfigurationService` selects between manifest-based (dev) and gateway-based (prod) configuration loading based on environment.

## Data Flow

### Agent Invocation Tracing Flow

```
Application
    │
    ▼
BaggageBuilder.set_request_context()     ← Set tenant, agent, correlation IDs
    │
    ▼
InvokeAgentScope.start()                 ← Create root span
    │
    ├──▶ SpanProcessor.on_start()        ← Copy baggage to span attributes
    │
    ▼
[Agent execution]
    │
    ├──▶ InferenceScope.start()          ← Child span for LLM calls
    │         └── record_input_tokens()
    │         └── record_output_tokens()
    │
    ├──▶ ExecuteToolScope.start()        ← Child span for tool execution
    │         └── record_response()
    │
    ▼
scope.record_response()                  ← Record final response
    │
    ▼
BatchSpanProcessor                       ← Accumulate spans
    │
    ▼
Agent365Exporter.export()                ← Send to backend
    ├── Partition by (tenant_id, agent_id)
    ├── Resolve endpoint via PowerPlatformApiDiscovery
    └── POST to /maven/agent365/agents/{agentId}/traces
```

### MCP Tool Discovery Flow

```
Application
    │
    ▼
McpToolServerConfigurationService.list_tool_servers()
    │
    ▼
_is_development_scenario()?
    │
    ├── YES ─▶ _load_servers_from_manifest()
    │              ├── Find ToolingManifest.json
    │              ├── Parse JSON configuration
    │              └── Return MCPServerConfig list
    │
    └── NO ──▶ _load_servers_from_gateway()
                   ├── Get gateway URL via get_tooling_gateway_for_digital_worker()
                   ├── HTTP GET with auth token
                   └── Return MCPServerConfig list
```

## Configuration

### Environment Variables

| Variable | Purpose | Values |
|----------|---------|--------|
| `ENVIRONMENT` | Controls development vs production behavior | `Development`, `Production` (default) |
| `ENABLE_OBSERVABILITY` | Enable OpenTelemetry tracing | `true`, `false` |
| `ENABLE_A365_OBSERVABILITY` | Enable Agent365-specific tracing | `true`, `false` |
| `ENABLE_A365_OBSERVABILITY_EXPORTER` | Enable backend exporter | `true`, `false` |
| `AGENT365_PYTHON_SDK_PACKAGE_VERSION` | Build version for packages | Semantic version string |

### Exporter Options

```python
from microsoft_agents_a365.observability.core import configure

configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    token_resolver=lambda agent_id, tenant_id: get_token(),
    cluster_category="prod",  # or "ppe", "test"
    # Advanced options via exporter_options parameter:
    # max_queue_size=2048,
    # scheduled_delay_ms=5000,
    # exporter_timeout_ms=30000,
    # max_export_batch_size=512,
)
```

## Testing

### Test Structure

```
tests/
├── observability/
│   ├── core/
│   │   ├── test_agent365.py                    # Configuration tests
│   │   ├── test_invoke_agent_scope.py          # Agent invocation tests
│   │   ├── test_execute_tool_scope.py          # Tool execution tests
│   │   ├── test_inference_scope.py             # Inference tests
│   │   ├── test_agent365_exporter.py           # Exporter tests
│   │   ├── test_span_processor.py              # Span processor tests
│   │   └── test_baggage_builder.py             # Context propagation tests
│   └── extensions/
│       ├── openai/
│       ├── langchain/
│       └── agentframework/
├── runtime/
│   ├── test_power_platform_api_discovery.py
│   ├── test_utility.py
│   └── test_environment_utils.py
└── tooling/
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=libraries --cov-report=html

# Run specific module tests
pytest tests/observability/core/ -v

# Run only unit tests
pytest tests/ -m unit

# Run only integration tests
pytest tests/ -m integration
```

### Test Conventions

- **Framework**: pytest with pytest-asyncio for async tests
- **Pattern**: AAA (Arrange → Act → Assert)
- **Naming**: `test_<method>_<condition>_<expected_result>`
- **Markers**: `@pytest.mark.unit` for fast tests, `@pytest.mark.integration` for slower tests

## Development

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- Git

### Setup

```bash
# Clone repository
git clone https://github.com/microsoft/Agent365-python.git
cd Agent365-python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies with uv
uv sync

# Or with pip
pip install -e "libraries/microsoft-agents-a365-observability-core[dev]"
```

### Building

```bash
# Set version
export AGENT365_PYTHON_SDK_PACKAGE_VERSION="0.1.0"

# Build all packages
uv build --all-packages --wheel
```

### Code Quality

The project uses [ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check linting
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Ruff Configuration** (from `pyproject.toml`):
- Line length: 100 characters
- Target: Python 3.11+
- Enabled rules: pycodestyle (E, W), Pyflakes (F), isort (I), flake8-bugbear (B), flake8-comprehensions (C4), pyupgrade (UP), copyright (CPY)

### Package Dependencies

Dependencies between packages are managed via uv workspace:

```
observability-core ◄─── observability-extensions-*
                   ◄─── observability-hosting
        │
        ▼
     runtime ◄─── tooling
                     │
                     ▼
              tooling-extensions-*
```

## Key Files Reference

| File | Purpose |
|------|---------|
| [pyproject.toml](../pyproject.toml) | Workspace configuration, dev dependencies, ruff config |
| [libraries/microsoft-agents-a365-observability-core/microsoft_agents_a365/observability/core/__init__.py](../libraries/microsoft-agents-a365-observability-core/microsoft_agents_a365/observability/core/__init__.py) | Observability public API |
| [libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/__init__.py](../libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/__init__.py) | Tooling public API |
| [libraries/microsoft-agents-a365-runtime/microsoft_agents_a365/runtime/__init__.py](../libraries/microsoft-agents-a365-runtime/microsoft_agents_a365/runtime/__init__.py) | Runtime public API |
| [libraries/microsoft-agents-a365-notifications/microsoft_agents_a365/notifications/__init__.py](../libraries/microsoft-agents-a365-notifications/microsoft_agents_a365/notifications/__init__.py) | Notifications public API |
| [tests/TEST_PLAN.md](../tests/TEST_PLAN.md) | Testing strategy and roadmap |

## External Resources

- [Microsoft Agent 365 Developer Documentation](https://learn.microsoft.com/microsoft-agent-365/developer/)
- [Microsoft 365 Agents SDK Documentation](https://learn.microsoft.com/microsoft-365/agents-sdk/)
- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [Sample Applications](https://github.com/microsoft/Agent365-Samples/tree/main/python)
- [GitHub Issues](https://github.com/microsoft/Agent365-python/issues)

# Microsoft Agent 365 Observability

This package provides telemetry, tracing, and monitoring components for AI agents built on OpenTelemetry.

This package adds structured spans for agent invocation, tool execution, and LLM inference, and can export them via a custom Agent365 exporter or fall back to console output for development.

## Features

* Automatic propagation of context (baggage) values onto span attributes
* Fine‑grained scopes for agent invocation, tool execution, and inference calls
* Pluggable exporter
* Safe, no‑op mode when observability is disabled

## Installation

```bash
pip install microsoft-agents-a365-observability-core
```

## Core Environment Variables

Set these (e.g. in a `.env` file or your hosting environment) before configuring:

```properties
ENABLE_OBSERVABILITY=true                  # Turns on tracing & span creation
ENABLE_A365_OBSERVABILITY_EXPORTER=true    # Use Agent365 exporter (otherwise falls back to ConsoleSpanExporter)
PYTHON_ENVIRONMENT=production              # Or development; influences target cluster/category resolution
```

Prefer the canonical `ENABLE_A365_OBSERVABILITY_EXPORTER`. If you omit `ENABLE_OBSERVABILITY` or set it to false, scopes become no‑ops and no spans are recorded.

## Configuration

Use `configure` to set up the tracer provider and span processors. You must provide a `service_name` and `service_namespace`.

### Minimal configuration (no custom exporter)

```python
from microsoft_agents_a365.observability.core import config

config.configure(
    service_name="my-agent-service",
    service_namespace="my.namespace"
)

tracer = config.get_tracer()
```

When neither `ENABLE_A365_OBSERVABILITY_EXPORTER` nor any legacy alias is truthy, or a required token resolver is missing, the SDK falls back to `ConsoleSpanExporter` and logs warnings. Legacy usage triggers a deprecation warning.

### Configuration with Agent365 exporter

The Agent365 exporter requires a `token_resolver` callback that can return an auth token given `(agent_id, tenant_id)` plus the cluster category (defaults to `preprod`).

```python
from microsoft_agents_a365.observability.core import config

def token_resolver(agent_id: str, tenant_id: str) -> str | None:
    # Implement secure token retrieval here
    return "Bearer <token>"

config.configure(
    service_name="my-agent-service",
    service_namespace="my.namespace",
    token_resolver=token_resolver,       # enables exporter if ENABLE_A365_OBSERVABILITY_EXPORTER or legacy alias is true
    cluster_category="preprod"          # or "prod"
)
```

### Exporter Setup Essentials

Agent365 exporter activation logic:

1. `ENABLE_A365_OBSERVABILITY_EXPORTER` (canonical) or any legacy alias is truthy (`true`, `1`, `yes`, `on`).
2. A non-None `token_resolver` is passed to `configure`.
3. Environment determines cluster category (overridden by explicit `cluster_category`).

If any prerequisite fails, console export is used. No code changes required.

## Baggage to Span Attributes

The custom `SpanProcessor` copies all non-empty baggage entries to newly started spans without overwriting existing attributes.

Helper builder:

```python
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder

with (
    BaggageBuilder()
    .tenant_id("tenant-123")
    .agent_id("agent-456")
    .correlation_id("corr-789")
    .build()
):
    # Any spans started in this context will receive these as attributes
    pass
```

## Scopes Overview

The SDK provides three high-level scope types (context managers) that start and end spans automatically:

| Scope | Purpose | Typical Use |
|-------|---------|-------------|
| `InvokeAgentScope` | Agent invocation lifecycle | Wrap an agent invocation at the start of workflow |
| `ExecuteToolScope` | Tool / function execution | Wrap execution of a tool inside an agent workflow |
| `InferenceScope` | LLM inference / completion | Wrap a model inference request |

Each exposes a static `start(...)` returning a context manager.

### InvokeAgentScope Usage

```python
from microsoft_agents_a365.observability.core.invoke_agent_scope import InvokeAgentScope
from microsoft_agents_a365.observability.core.invoke_agent_details import InvokeAgentDetails
from microsoft_agents_a365.observability.core.tenant_details import TenantDetails
from microsoft_agents_a365.observability.core.request import Request

invoke_details = InvokeAgentDetails(
    details=agent_details,        # AgentDetails instance
    endpoint=my_endpoint,         # Optional endpoint (with hostname/port)
    session_id="session-42"
)
tenant_details = TenantDetails(tenant_id="tenant-123")
req = Request(content="User asks a question")

with InvokeAgentScope.start(invoke_details, tenant_details, req):
    # Perform agent invocation logic
    response = call_agent(...)
```

Tags automatically set (when values present): agent id/name/description, session id, request content, server address/port.

### ExecuteToolScope Usage

```python
from microsoft_agents_a365.observability.core.execute_tool_scope import ExecuteToolScope
from microsoft_agents_a365.observability.core.tool_call_details import ToolCallDetails

tool_details = ToolCallDetails(
    tool_name="summarize",
    tool_type="function",
    tool_call_id="tc-001",
    arguments="{'text': '...'}",
    description="Summarize provided text",
    endpoint=None  # or endpoint object with hostname/port
)

with ExecuteToolScope.start(tool_details, agent_details, tenant_details):
    result = run_tool(tool_details)
```

Tags: tool name, arguments, type, call id, description, server address/port.

### InferenceScope Usage

```python
from microsoft_agents_a365.observability.core.inference_scope import InferenceScope
from microsoft_agents_a365.observability.core.inference_call_details import InferenceCallDetails
from microsoft_agents_a365.observability.core.request import Request

inference_details = InferenceCallDetails(
    operationName=SomeEnumOrValue("chat"),
    model="gpt-4o-mini",
    providerName="azure-openai",
    inputTokens=123,
    outputTokens=456,
    finishReasons=["stop"],
    responseId="resp-987"
)
req = Request(content="Explain quantum computing simply.")

with InferenceScope.start(inference_details, agent_details, tenant_details, req):
    completion = call_llm(...)
```

Tags: model, provider name, request content, input/output tokens, finish reasons, response id.

## Disabling Observability

Set `ENABLE_OBSERVABILITY=false` (or remove it). Scopes still usable but no spans or exports occur.

## Best Practices

* Create scopes as narrow as possible (only the work you want timed).
* Use baggage for cross-cutting identifiers (tenant, correlation id) rather than manually setting on every scope.

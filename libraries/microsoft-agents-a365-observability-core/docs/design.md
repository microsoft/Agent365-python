# Observability Core - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-observability-core` package.

## Overview

The observability core package provides OpenTelemetry-based distributed tracing infrastructure for AI agent applications. It enables comprehensive observability by tracing agent invocations, LLM inference calls, and tool executions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Public API                                │
│  configure() | get_tracer() | InvokeAgentScope | BaggageBuilder │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TelemetryManager                             │
│              (Thread-safe Singleton)                             │
│  - TracerProvider management                                     │
│  - SpanProcessor registration                                    │
│  - Exporter configuration                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐ ┌────────────────────────┐ ┌──────────────────┐
│  SpanProcessor   │ │_EnrichingBatchSpan     │ │ Agent365Exporter │
│ (Custom baggage  │ │Processor               │ │ (HTTP export)    │
│  propagation)    │ │(enricher hook + batch) │ │                  │
└──────────────────┘ └────────────────────────┘ └──────────────────┘
                              │
                              ▼ (optional)
                     ┌──────────────────┐
                     │ span_enricher()  │
                     │ (registered by   │
                     │  extensions)     │
                     └──────────────────┘
```

## Key Components

### Configuration ([config.py](../microsoft_agents_a365/observability/core/config.py))

The `TelemetryManager` class is a thread-safe singleton that manages telemetry configuration:

```python
from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.exporters import Agent365ExporterOptions

# Preferred: use exporter_options
configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    exporter_options=Agent365ExporterOptions(
        token_resolver=lambda agent_id, tenant_id: get_token(),
        cluster_category="prod",
    ),
    suppress_invoke_agent_input=False,
)

# Legacy (deprecated): token_resolver and cluster_category as top-level params
configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    token_resolver=lambda agent_id, tenant_id: get_token(),
    cluster_category="prod",
)
```

**Key behaviors:**
- Creates or reuses an existing `TracerProvider`
- Adds `_EnrichingBatchSpanProcessor` (extension hook + batching) for span export
- Adds custom `SpanProcessor` for baggage-to-attribute copying
- Falls back to `ConsoleSpanExporter` if token resolver is not provided
- `suppress_invoke_agent_input=True` omits input message attributes from child spans of `InvokeAgentScope`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service_name` | `str` | Name of the service (recorded in resource attributes) |
| `service_namespace` | `str` | Namespace of the service |
| `logger_name` | `str` | Logger name to configure (defaults to module name) |
| `exporter_options` | `Agent365ExporterOptions` | Preferred: full exporter configuration |
| `token_resolver` | `Callable` | *Deprecated* – use `exporter_options.token_resolver` |
| `cluster_category` | `str` | *Deprecated* – use `exporter_options.cluster_category` |
| `suppress_invoke_agent_input` | `bool` | If `True`, suppress input messages on child spans |

### Scope Classes

#### Base Class ([opentelemetry_scope.py](../microsoft_agents_a365/observability/core/opentelemetry_scope.py))

`OpenTelemetryScope` is the base class for all tracing scopes:

```python
class OpenTelemetryScope:
    """Base class for OpenTelemetry tracing scopes."""

    def __init__(self, kind, operation_name, activity_name, agent_details, tenant_details):
        # Creates span with given parameters
        # Sets common attributes (gen_ai.system, operation name)
        # Sets agent/tenant details as span attributes

    def __enter__(self):
        # Makes span active in current context

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Records exception if occurred
        # Restores previous context
        # Ends span
```

**Methods:**
| Method | Purpose |
|--------|---------|
| `record_error(exception)` | Record exception with status ERROR |
| `record_response(response)` | Record response content as attribute |
| `record_cancellation()` | Record task cancellation |
| `set_tag_maybe(name, value)` | Set attribute if value is not None |
| `add_baggage(key, value)` | Add baggage to current context |
| `record_attributes(attrs)` | Set multiple attributes at once |

#### InvokeAgentScope ([invoke_agent_scope.py](../microsoft_agents_a365/observability/core/invoke_agent_scope.py))

Traces agent invocation operations (entry point for agent requests):

```python
from microsoft_agents_a365.observability.core import (
    InvokeAgentScope,
    InvokeAgentDetails,
    TenantDetails,
    AgentDetails,
)
from microsoft_agents_a365.observability.core.models.caller_details import CallerDetails

with InvokeAgentScope.start(
    invoke_agent_details=InvokeAgentDetails(
        endpoint=parsed_url,
        session_id="session-123",
        details=AgentDetails(agent_id="agent-456", agent_name="MyAgent")
    ),
    tenant_details=TenantDetails(tenant_id="tenant-789"),
    request=Request(content="Hello", execution_type=ExecutionType.CHAT),
    caller_agent_details=AgentDetails(agent_id="caller-agent-id"),  # optional
    caller_details=CallerDetails(caller_id="user-abc"),             # optional
) as scope:
    # Agent processing
    scope.record_response("Agent response")
    scope.record_input_messages(["User question"])
    scope.record_output_messages(["Agent answer"])
```

**Span attributes recorded:**
- Server address and port
- Session ID
- Execution source metadata
- Execution type
- Input/output messages
- Caller details (if provided): ID, UPN, name, user ID, tenant ID
- Caller agent details (if provided): name, ID, type, blueprint ID, AUID (agent unique ID), UPN, tenant ID, client IP

#### InferenceScope ([inference_scope.py](../microsoft_agents_a365/observability/core/inference_scope.py))

Traces LLM/AI model inference calls:

```python
from microsoft_agents_a365.observability.core import InferenceScope, InferenceCallDetails

with InferenceScope.start(
    inference_call_details=InferenceCallDetails(
        model_name="gpt-4",
        provider="openai"
    ),
    agent_details=agent_details,
    tenant_details=tenant_details,
) as scope:
    # LLM call
    scope.record_input_tokens(100)
    scope.record_output_tokens(50)
    scope.record_finish_reasons(["stop"])
```

#### ExecuteToolScope ([execute_tool_scope.py](../microsoft_agents_a365/observability/core/execute_tool_scope.py))

Traces tool execution operations:

```python
from microsoft_agents_a365.observability.core import ExecuteToolScope, ToolCallDetails

with ExecuteToolScope.start(
    tool_call_details=ToolCallDetails(
        tool_name="search",
        tool_arguments={"query": "weather"}
    ),
    agent_details=agent_details,
    tenant_details=tenant_details,
) as scope:
    # Tool execution
    scope.record_response("Tool result")
```

#### OutputScope ([spans_scopes/output_scope.py](../microsoft_agents_a365/observability/core/spans_scopes/output_scope.py))

Traces outbound message delivery from an agent. Used internally to record response messages sent back to callers:

```python
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from microsoft_agents_a365.observability.core.models.response import Response

with OutputScope.start(
    agent_details=agent_details,
    tenant_details=tenant_details,
    response=Response(messages=["Initial response"]),
    parent_id="parent-activity-id",  # optional: link to upstream span
) as scope:
    # Record additional messages as they arrive
    scope.record_output_messages(["Additional message chunk"])
```

**Key behavior:**
- Initializes with messages from the `Response` object
- `record_output_messages()` appends to the accumulated list and updates the span attribute
- `parent_id` allows linking to an upstream activity for cross-service correlation

### Context Propagation ([middleware/baggage_builder.py](../microsoft_agents_a365/observability/core/middleware/baggage_builder.py))

`BaggageBuilder` provides a fluent API for setting OpenTelemetry baggage values:

```python
from microsoft_agents_a365.observability.core import BaggageBuilder

# Full builder pattern
with BaggageBuilder() \
    .tenant_id("tenant-123") \
    .agent_id("agent-456") \
    .correlation_id("corr-789") \
    .caller_id("user-abc") \
    .session_id("session-xyz") \
    .build():
    # All child spans inherit this baggage
    pass

# Convenience method for common fields
with BaggageBuilder.set_request_context(
    tenant_id="tenant-123",
    agent_id="agent-456",
    correlation_id="corr-789"
):
    pass
```

**Available baggage setters:**
| Method | Baggage Key |
|--------|-------------|
| `tenant_id(value)` | `tenant_id` |
| `agent_id(value)` | `gen_ai.agent.id` |
| `agent_auid(value)` | `gen_ai.agent.auid` |
| `agent_upn(value)` | `gen_ai.agent.upn` |
| `correlation_id(value)` | `correlation_id` |
| `caller_id(value)` | `gen_ai.caller.id` |
| `session_id(value)` | `session_id` |
| `conversation_id(value)` | `gen_ai.conversation.id` |
| `channel_name(value)` | `gen_ai.execution.source.name` |

### Span Processor ([trace_processor/span_processor.py](../microsoft_agents_a365/observability/core/trace_processor/span_processor.py))

Custom `SpanProcessor` that copies baggage entries to span attributes on span start:

```python
class SpanProcessor(OtelSpanProcessor):
    def on_start(self, span, parent_context):
        # Copy all baggage entries to span attributes
        for key, value in baggage.get_all(parent_context).items():
            span.set_attribute(key, value)
```

This ensures that context values set via `BaggageBuilder` are recorded as span attributes.

### Exporter ([exporters/agent365_exporter.py](../microsoft_agents_a365/observability/core/exporters/agent365_exporter.py))

`_Agent365Exporter` exports spans to the Agent365 backend:

**Export flow:**
1. Partition spans by `(tenant_id, agent_id)` tuple
2. For each partition:
   - Resolve endpoint via `PowerPlatformApiDiscovery`
   - Resolve auth token via `token_resolver(agent_id, tenant_id)`
   - Build OTLP-like JSON payload
   - POST to `/maven/agent365/agents/{agentId}/traces`
3. Retry transient failures (408, 429, 5xx) up to 3 times with exponential backoff

**Configuration via `Agent365ExporterOptions`:**
```python
from microsoft_agents_a365.observability.core.exporters import Agent365ExporterOptions

options = Agent365ExporterOptions(
    cluster_category="prod",
    token_resolver=my_token_resolver,
    use_s2s_endpoint=False,
    max_queue_size=2048,
    scheduled_delay_ms=5000,
    exporter_timeout_ms=30000,
    max_export_batch_size=512,
)
```

### Span Enrichment ([exporters/enriching_span_processor.py](../microsoft_agents_a365/observability/core/exporters/enriching_span_processor.py) and [exporters/enriched_span.py](../microsoft_agents_a365/observability/core/exporters/enriched_span.py))

`_EnrichingBatchSpanProcessor` wraps OpenTelemetry's `BatchSpanProcessor` and applies a registered enricher function to every span before batching and exporting. Only one enricher can be active at a time (one platform instrumentor per process).

`EnrichedReadableSpan` is a wrapper around `ReadableSpan` that merges extra attributes into the immutable span without modifying it in place.

**How extensions register an enricher:**

```python
from microsoft_agents_a365.observability.core import (
    register_span_enricher,
    unregister_span_enricher,
    EnrichedReadableSpan,
)
from opentelemetry.sdk.trace import ReadableSpan

def my_enricher(span: ReadableSpan) -> ReadableSpan:
    """Add platform-specific attributes before export."""
    extra = {"gen_ai.platform.version": "1.2.3"}
    return EnrichedReadableSpan(span, extra)

# During instrumentation setup:
register_span_enricher(my_enricher)

# During uninstrumentation teardown:
unregister_span_enricher()
```

**Enrichment functions:**

| Function | Purpose |
|----------|---------|
| `register_span_enricher(fn)` | Register enricher; raises `RuntimeError` if one is already registered |
| `unregister_span_enricher()` | Remove the current enricher |
| `get_span_enricher()` | Return the current enricher (or `None`) |

## Data Classes

### InvokeAgentDetails

```python
@dataclass
class InvokeAgentDetails:
    endpoint: ParseResult | None  # Parsed URL of the agent endpoint
    session_id: str | None        # Session identifier
    details: AgentDetails         # Agent metadata
```

### AgentDetails

```python
@dataclass
class AgentDetails:
    agent_id: str | None
    agent_name: str | None
    agent_description: str | None
    agent_auid: str | None        # Agent unique identifier
    agent_upn: str | None         # User principal name
    agent_blueprint_id: str | None
    agent_type: AgentType | None
    tenant_id: str | None
    conversation_id: str | None
    icon_uri: str | None
```

### TenantDetails

```python
@dataclass
class TenantDetails:
    tenant_id: str | None
```

### CallerDetails

```python
@dataclass
class CallerDetails:
    caller_id: str | None       # Unique identifier for the caller
    caller_upn: str | None      # User Principal Name of the caller
    caller_name: str | None     # Human-readable name of the caller
    caller_user_id: str | None  # User ID of the caller
    tenant_id: str | None       # Tenant ID of the caller
```

### InferenceCallDetails

```python
@dataclass
class InferenceCallDetails:
    model_name: str | None
    provider: str | None
    # Additional inference metadata
```

### ToolCallDetails

```python
@dataclass
class ToolCallDetails:
    tool_name: str | None
    tool_arguments: dict | None
    tool_endpoint: str | None
    tool_type: ToolType | None
```

### Response

```python
@dataclass
class Response:
    messages: list[str]  # Response messages from agent execution
```

## Enums

| Enum | Values | Purpose |
|------|--------|---------|
| `ExecutionType` | `CHAT`, `STREAMING`, ... | Type of agent request |
| `InferenceOperationType` | `CHAT`, `COMPLETION`, ... | Type of LLM inference call |
| `ToolType` | `FUNCTION`, `MCP`, ... | Type of tool being executed |
| `AgentType` | `` `ENTRA_EMBODIED` ``, `` `ENTRA_NON_EMBODIED` ``, `` `MICROSOFT_COPILOT` ``, `` `DECLARATIVE_AGENT` ``, `` `FOUNDRY` `` | Supported agent types for generative AI |
| `OperationSource` | `SDK`, `GATEWAY`, `MCP_SERVER` | Source of the operation being traced |

## Environment Variables

| Variable | Purpose | Values |
|----------|---------|--------|
| `ENABLE_OBSERVABILITY` | Enable OpenTelemetry tracing | `true`, `false` |
| `ENABLE_A365_OBSERVABILITY` | Enable Agent365-specific tracing | `true`, `false` |
| `ENABLE_A365_OBSERVABILITY_EXPORTER` | Enable Agent365 backend exporter | `true`, `false` |

## Design Patterns

### Singleton Pattern

`TelemetryManager` uses double-checked locking for thread-safe singleton initialization:

```python
class TelemetryManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

### Context Manager Pattern

All scope classes implement `__enter__` and `__exit__` for automatic span lifecycle:

```python
with InvokeAgentScope.start(...) as scope:
    # Span is active
    scope.record_response("result")
# Span automatically ends, errors recorded if exception raised
```

### Builder Pattern

`BaggageBuilder` uses method chaining for fluent configuration:

```python
builder = BaggageBuilder().tenant_id("t").agent_id("a").build()
```

## File Structure

```
microsoft_agents_a365/observability/core/
├── __init__.py                    # Public API exports
├── config.py                      # TelemetryManager singleton
├── opentelemetry_scope.py         # Base scope class
├── invoke_agent_scope.py          # Agent invocation tracing
├── inference_scope.py             # LLM inference tracing
├── execute_tool_scope.py          # Tool execution tracing
├── agent_details.py               # AgentDetails dataclass
├── tenant_details.py              # TenantDetails dataclass
├── invoke_agent_details.py        # InvokeAgentDetails dataclass
├── inference_call_details.py      # InferenceCallDetails dataclass
├── tool_call_details.py           # ToolCallDetails dataclass
├── request.py                     # Request dataclass
├── source_metadata.py             # SourceMetadata dataclass
├── execution_type.py              # ExecutionType enum
├── inference_operation_type.py    # InferenceOperationType enum
├── tool_type.py                   # ToolType enum
├── constants.py                   # Attribute key constants
├── utils.py                       # Utility functions
├── middleware/
│   ├── __init__.py
│   └── baggage_builder.py         # BaggageBuilder and BaggageScope
├── spans_scopes/
│   ├── __init__.py
│   └── output_scope.py            # OutputScope for outbound message tracing
├── trace_processor/
│   ├── __init__.py
│   ├── span_processor.py          # Custom SpanProcessor
│   └── util.py                    # Processor utilities
├── exporters/
│   ├── __init__.py
│   ├── agent365_exporter.py       # Agent365 backend exporter
│   ├── agent365_exporter_options.py  # Exporter configuration
│   ├── enriched_span.py           # EnrichedReadableSpan wrapper
│   ├── enriching_span_processor.py   # _EnrichingBatchSpanProcessor + enricher registry
│   └── utils.py                   # Exporter utilities
└── models/
    ├── __init__.py
    ├── agent_type.py              # AgentType enum
    ├── caller_details.py          # CallerDetails dataclass
    ├── operation_source.py        # OperationSource enum
    └── response.py                # Response dataclass
```

## Testing

Tests are located in `tests/observability/core/`:

```bash
# Run all observability core tests
pytest tests/observability/core/ -v

# Run specific test file
pytest tests/observability/core/test_invoke_agent_scope.py -v
```

## Dependencies

- `opentelemetry-api` - OpenTelemetry API interfaces
- `opentelemetry-sdk` - OpenTelemetry SDK implementation
- `requests` - HTTP client for exporter
- `microsoft-agents-a365-runtime` - Endpoint discovery utilities

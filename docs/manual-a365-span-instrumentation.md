# Manual Agent 365 span instrumentation (without the SDK)

This guide documents the **attribute contract** and **export protocol** for making your OpenTelemetry spans compatible with the Agent 365 observability backend — without importing any `microsoft-agents-a365-*` package.

## When to use this guide

Use this guide if you:

- Have an existing Python application already instrumented with OpenTelemetry
- Want your agent spans to appear in the Agent 365 portal
- Prefer not to add the Agent 365 SDK as a dependency

**When to use the SDK instead:** If you're starting fresh or can accept the dependency, the SDK (`microsoft-agents-a365-observability-core`) handles all of this automatically — attribute setting, span lifecycle, export, retries, and payload chunking. See [Integrating with existing OpenTelemetry](./integrating-with-existing-opentelemetry.md).

## Prerequisites

- Python 3.11+
- `opentelemetry-sdk` (any recent version)
- `requests` (for manual export to the A365 backend)
- A registered Agent 365 agent (you'll need the `tenant_id` and `agent_id`)
- A token resolver that can produce a Bearer token for the A365 ingestion endpoint

Install dependencies:

```bash
pip install opentelemetry-sdk opentelemetry-api requests
```

## Attribute contract

The Agent 365 backend filters spans by `gen_ai.operation.name` and routes them by `microsoft.tenant.id` + `gen_ai.agent.id`. Spans missing required attributes are silently dropped.

### Accepted `gen_ai.operation.name` values

Only spans with one of these values pass the backend's ingest filter:

| Value | Span type |
|-------|-----------|
| `invoke_agent` | Top-level agent invocation |
| `Chat` | Inference (manual instrumentation convention) |
| `chat` | Inference (OTel GenAI semconv / auto-instrumentation) |
| `TextCompletion` | Inference (text completion) |
| `GenerateContent` | Inference (content generation) |
| `execute_tool` | Tool execution |

### `invoke_agent` span

The top-level span representing one user turn / agent invocation.

| Tier | Attribute | Expected value | Notes |
|------|-----------|----------------|-------|
| **Required** | `gen_ai.operation.name` | `"invoke_agent"` | Must match exactly |
| **Required** | `microsoft.tenant.id` | Tenant GUID | Used for routing |
| **Required** | `gen_ai.agent.id` | Agent GUID | Used for routing |
| Recommended | `gen_ai.agent.name` | Human-readable agent name | Displayed in portal |
| Recommended | `microsoft.session.id` | Session identifier | Groups turns in portal |
| Recommended | `gen_ai.conversation.id` | Conversation identifier | Thread grouping |
| Recommended | `microsoft.a365.agent.blueprint.id` | Blueprint GUID | Links to agent definition |
| Recommended | `microsoft.a365.agent.platform.id` | Platform identifier | Identifies hosting platform |
| Recommended | `user.id` | End-user identifier | Portal user analytics |
| Recommended | `server.address` | Server hostname | |
| Optional | `gen_ai.agent.description` | Agent description | |
| Optional | `gen_ai.agent.version` | Agent version string | |
| Optional | `microsoft.agent.user.id` | Agent's service identity | |
| Optional | `microsoft.agent.user.email` | Agent's service email | |
| Optional | `user.email` | End-user email | |
| Optional | `user.name` | End-user display name | |
| Optional | `client.address` | Client IP or hostname | |
| Optional | `microsoft.channel.name` | Channel (e.g. `"Teams"`, `"Webchat"`) | |
| Optional | `microsoft.channel.link` | Channel URL | |
| Optional | `gen_ai.input.messages` | JSON-serialized input messages | Can be large; may be truncated |
| Optional | `microsoft.a365.caller.agent.name` | Calling agent name | For agent-to-agent calls |
| Optional | `microsoft.a365.caller.agent.id` | Calling agent GUID | For agent-to-agent calls |
| Optional | `microsoft.a365.caller.agent.blueprint.id` | Calling agent blueprint | For agent-to-agent calls |

### `inference` span (LLM call)

Child of `invoke_agent`. One per LLM inference call.

| Tier | Attribute | Expected value | Notes |
|------|-----------|----------------|-------|
| **Required** | `gen_ai.operation.name` | `"Chat"` or `"TextCompletion"` or `"GenerateContent"` | See accepted values above |
| **Required** | `microsoft.tenant.id` | Tenant GUID | Same as parent |
| **Required** | `gen_ai.agent.id` | Agent GUID | Same as parent |
| **Required** | `gen_ai.request.model` | Model name (e.g. `"gpt-4o"`) | |
| Recommended | `gen_ai.usage.input_tokens` | Integer | Token billing/monitoring |
| Recommended | `gen_ai.usage.output_tokens` | Integer | Token billing/monitoring |
| Recommended | `gen_ai.response.finish_reasons` | JSON array (e.g. `["stop"]`) | |
| Recommended | `gen_ai.conversation.id` | Conversation identifier | |
| Recommended | `gen_ai.provider.name` | `"openai"`, `"azure"`, etc. | |
| Optional | `gen_ai.input.messages` | JSON-serialized input messages | |
| Optional | `gen_ai.output.messages` | JSON-serialized output messages | |
| Optional | `server.address` | LLM endpoint hostname | |
| Optional | `server.port` | LLM endpoint port | Omit if 443 |
| Optional | `microsoft.a365.agent.thought.process` | Agent reasoning trace | |

### `execute_tool` span

Child of `invoke_agent`. One per tool invocation.

| Tier | Attribute | Expected value | Notes |
|------|-----------|----------------|-------|
| **Required** | `gen_ai.operation.name` | `"execute_tool"` | Must match exactly |
| **Required** | `microsoft.tenant.id` | Tenant GUID | Same as parent |
| **Required** | `gen_ai.agent.id` | Agent GUID | Same as parent |
| **Required** | `gen_ai.tool.name` | Tool function name | |
| Recommended | `gen_ai.tool.call.id` | Tool call ID from LLM response | |
| Recommended | `gen_ai.tool.call.arguments` | JSON-serialized arguments | |
| Recommended | `gen_ai.tool.call.result` | JSON-serialized result | Set after execution |
| Recommended | `gen_ai.conversation.id` | Conversation identifier | |
| Optional | `gen_ai.tool.type` | `"function"` | |
| Optional | `gen_ai.tool.description` | Tool description | |
| Optional | `server.address` | Server hostname | |

### Resource attributes

Set these on your `TracerProvider`'s `Resource`:

| Tier | Attribute | Expected value |
|------|-----------|----------------|
| **Required** | `service.name` | Your service/agent name |
| Recommended | `service.namespace` | Your service namespace |

### SDK-identifying attributes (optional)

Set these on every span to identify your telemetry source:

| Attribute | Value |
|-----------|-------|
| `telemetry.sdk.name` | `"A365ObservabilitySDK"` (or your own identifier) |
| `telemetry.sdk.language` | `"python"` |
| `telemetry.sdk.version` | Your version string |

## Examples

### Example 1: Minimal `invoke_agent` span

Creates a single root span with only the required attributes and exports to console for verification.

```python
import json
import uuid

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# --- Configuration (replace with your values) ---
TENANT_ID = "your-tenant-guid"
AGENT_ID = "your-agent-guid"
AGENT_NAME = "my-weather-agent"

# --- Set up OpenTelemetry with console export ---
resource = Resource.create({"service.name": AGENT_NAME})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("my-agent-instrumentation", "1.0.0")

# --- Create an invoke_agent span ---
with tracer.start_as_current_span(
    name=f"invoke_agent {AGENT_NAME}",
    kind=trace.SpanKind.INTERNAL,
) as span:
    # Required attributes
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("microsoft.tenant.id", TENANT_ID)
    span.set_attribute("gen_ai.agent.id", AGENT_ID)

    # Recommended attributes
    span.set_attribute("gen_ai.agent.name", AGENT_NAME)
    span.set_attribute("microsoft.session.id", str(uuid.uuid4()))
    span.set_attribute("gen_ai.conversation.id", str(uuid.uuid4()))

    # ... your agent logic here ...
    print("Agent invoked successfully")

# Flush to ensure spans are exported
provider.force_flush()
```

Run this and you should see a JSON span dump on stdout with `gen_ai.operation.name: invoke_agent`.

### Example 2: Full agent turn with span hierarchy

Creates the proper parent-child relationship: `invoke_agent` → `inference` + `execute_tool`.

```python
import json
import uuid

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# --- Configuration ---
TENANT_ID = "your-tenant-guid"
AGENT_ID = "your-agent-guid"
AGENT_NAME = "my-weather-agent"
MODEL_NAME = "gpt-4o"
PROVIDER_NAME = "azure"

# --- OpenTelemetry setup ---
resource = Resource.create({
    "service.name": AGENT_NAME,
    "service.namespace": "my-namespace",
})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("my-agent-instrumentation", "1.0.0")

# --- Simulate an agent turn ---
session_id = str(uuid.uuid4())
conversation_id = str(uuid.uuid4())
user_message = "What's the weather in Seattle?"


def get_weather(city: str) -> str:
    """Simulated tool."""
    return json.dumps({"city": city, "temp_f": 62, "condition": "cloudy"})


# Top-level: invoke_agent
with tracer.start_as_current_span(
    name=f"invoke_agent {AGENT_NAME}",
    kind=trace.SpanKind.INTERNAL,
) as agent_span:
    agent_span.set_attribute("gen_ai.operation.name", "invoke_agent")
    agent_span.set_attribute("microsoft.tenant.id", TENANT_ID)
    agent_span.set_attribute("gen_ai.agent.id", AGENT_ID)
    agent_span.set_attribute("gen_ai.agent.name", AGENT_NAME)
    agent_span.set_attribute("microsoft.session.id", session_id)
    agent_span.set_attribute("gen_ai.conversation.id", conversation_id)
    agent_span.set_attribute("user.id", "user-123")
    agent_span.set_attribute("gen_ai.input.messages", json.dumps([
        {"role": "user", "content": user_message}
    ]))

    # Child: inference (LLM call)
    with tracer.start_as_current_span(
        name=f"Chat {MODEL_NAME}",
        kind=trace.SpanKind.INTERNAL,
    ) as inference_span:
        inference_span.set_attribute("gen_ai.operation.name", "Chat")
        inference_span.set_attribute("microsoft.tenant.id", TENANT_ID)
        inference_span.set_attribute("gen_ai.agent.id", AGENT_ID)
        inference_span.set_attribute("gen_ai.request.model", MODEL_NAME)
        inference_span.set_attribute("gen_ai.provider.name", PROVIDER_NAME)
        inference_span.set_attribute("gen_ai.conversation.id", conversation_id)
        inference_span.set_attribute("server.address", "my-resource.openai.azure.com")

        # ... call your LLM here ...
        # After response:
        inference_span.set_attribute("gen_ai.usage.input_tokens", 42)
        inference_span.set_attribute("gen_ai.usage.output_tokens", 15)
        inference_span.set_attribute("gen_ai.response.finish_reasons", json.dumps(["tool_calls"]))

    # Child: execute_tool
    tool_call_id = "call_abc123"
    tool_name = "get_weather"
    tool_args = json.dumps({"city": "Seattle"})

    with tracer.start_as_current_span(
        name=f"execute_tool {tool_name}",
        kind=trace.SpanKind.INTERNAL,
    ) as tool_span:
        tool_span.set_attribute("gen_ai.operation.name", "execute_tool")
        tool_span.set_attribute("microsoft.tenant.id", TENANT_ID)
        tool_span.set_attribute("gen_ai.agent.id", AGENT_ID)
        tool_span.set_attribute("gen_ai.tool.name", tool_name)
        tool_span.set_attribute("gen_ai.tool.call.id", tool_call_id)
        tool_span.set_attribute("gen_ai.tool.call.arguments", tool_args)
        tool_span.set_attribute("gen_ai.conversation.id", conversation_id)
        tool_span.set_attribute("gen_ai.tool.type", "function")

        # Execute the tool
        result = get_weather("Seattle")
        tool_span.set_attribute("gen_ai.tool.call.result", result)

provider.force_flush()
```

You should see three spans in the console output: `invoke_agent my-weather-agent` (root), `Chat gpt-4o` (child), and `execute_tool get_weather` (child). Verify that `parentSpanId` on the children matches the root's `spanId`.

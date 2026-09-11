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
| `output_messages` | Output message recording (agent response to user) |

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
| Optional | `gen_ai.output.messages` | JSON-serialized output messages | Agent's response; may be truncated |
| Optional | `server.port` | Server port number | Omit if 443 |
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
| Optional | `server.port` | Server port number | Omit if 443 |

### `output_messages` span

Child of `invoke_agent`. Records the agent's final response to the user.

| Tier | Attribute | Expected value | Notes |
|------|-----------|----------------|-------|
| **Required** | `gen_ai.operation.name` | `"output_messages"` | Must match exactly |
| **Required** | `microsoft.tenant.id` | Tenant GUID | Same as parent |
| **Required** | `gen_ai.agent.id` | Agent GUID | Same as parent |
| Recommended | `gen_ai.output.messages` | JSON-serialized output messages | The agent's response |
| Recommended | `gen_ai.conversation.id` | Conversation identifier | |
| Optional | `gen_ai.agent.name` | Agent name | Same as parent |

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

## Exporting to the Agent 365 backend

The Agent 365 backend does **not** accept standard OTLP protobuf or OTLP/HTTP JSON. It uses a custom OTLP-like JSON format. This section documents the HTTP contract.

### Endpoint

```
POST https://agent365.svc.cloud.microsoft/observability/tenants/{tenantId}/otlp/agents/{agentId}/traces?api-version=1
```

Replace `{tenantId}` and `{agentId}` with the values from your span attributes (`microsoft.tenant.id` and `gen_ai.agent.id`).

### Authentication

Every request requires a Bearer token:

```
Authorization: Bearer <token>
Content-Type: application/json
```

The token must be issued for an app registration that has the **`Agent365.Observability.OtelWrite`** application role (scope). Without this role, the backend returns `403 Forbidden`.

> **Important:** The `gen_ai.agent.id` value in your span attributes **must match** the application identity in the Bearer token. The backend validates that the agent ID in the payload corresponds to the authenticated app. Mismatches result in `403 Forbidden`.

The token is obtained from a **token resolver** — a function with signature:

```python
def resolve_token(agent_id: str, tenant_id: str) -> str | None:
    """Return a valid Bearer token for the given agent and tenant, or None if unavailable."""
    ...
```

If the token resolver returns `None`, the exporter should skip that batch and log a warning. How you implement this depends on your environment (MSAL client credentials, managed identity, etc.). The A365 SDK uses this same interface internally.

### Payload format

The body is JSON with this structure:

```json
{
  "resourceSpans": [
    {
      "resource": {
        "attributes": {
          "service.name": "my-agent",
          "service.namespace": "my-namespace"
        }
      },
      "scopeSpans": [
        {
          "scope": {
            "name": "my-agent-instrumentation",
            "version": "1.0.0"
          },
          "spans": [
            {
              "traceId": "0af7651916cd43dd8448eb211c80319c",
              "spanId": "b7ad6b7169203331",
              "parentSpanId": null,
              "name": "invoke_agent my-agent",
              "kind": "INTERNAL",
              "startTimeUnixNano": 1716000000000000000,
              "endTimeUnixNano": 1716000001000000000,
              "attributes": {
                "gen_ai.operation.name": "invoke_agent",
                "microsoft.tenant.id": "tenant-guid",
                "gen_ai.agent.id": "agent-guid"
              },
              "events": null,
              "links": null,
              "status": {
                "code": "OK",
                "message": ""
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `traceId` | string | 32 hex chars (128-bit trace ID) |
| `spanId` | string | 16 hex chars (64-bit span ID) |
| `parentSpanId` | string \| null | Parent's spanId, or null for root |
| `name` | string | Span name (see naming conventions below) |
| `kind` | string | Span kind name: `"INTERNAL"`, `"CLIENT"`, `"SERVER"`, etc. |
| `startTimeUnixNano` | integer | Start time in nanoseconds since Unix epoch |
| `endTimeUnixNano` | integer | End time in nanoseconds since Unix epoch |
| `attributes` | object \| null | Key-value map of span attributes |
| `events` | array \| null | Span events (exceptions, logs) |
| `links` | array \| null | Span links |
| `status.code` | string | `"UNSET"`, `"OK"`, or `"ERROR"` |
| `status.message` | string | Error description (empty for non-error) |

### Span name conventions

| Span type | Name format | Example |
|-----------|-------------|---------|
| invoke_agent | `"invoke_agent"` or `"invoke_agent <agent_name>"` | `"invoke_agent my-weather-agent"` |
| inference | `"<operation> <model>"` | `"Chat gpt-4o"` |
| execute_tool | `"execute_tool <tool_name>"` | `"execute_tool get_weather"` |

### Constraints

| Constraint | Value | Behavior |
|------------|-------|----------|
| Max payload size (server limit) | 1,000,000 bytes | Requests exceeding 1 MB are rejected |
| Recommended max payload | ~900,000 bytes | Use as conservative buffer below the 1 MB limit |
| Max individual span | 250,000 bytes | Truncate largest attributes (see below) |
| Retry on | 408, 429, 5xx | Exponential backoff; respect `Retry-After` header for 429 |
| Fail on | Other 4xx | Non-retryable; check auth and payload format |
| Timeout | 30 seconds | Per-request HTTP timeout |

#### Payload chunking

If a serialized batch exceeds ~900,000 bytes, split it into multiple POST requests. Each request must still respect the grouping requirement (same tenant + agent). A simple approach:

```python
def chunk_spans(spans: list[dict], max_bytes: int = 900_000) -> list[list[dict]]:
    """Split serialized spans into chunks that fit within the payload limit."""
    chunks = []
    current_chunk = []
    current_size = 0
    overhead = 200  # approximate envelope overhead

    for span in spans:
        span_size = len(json.dumps(span, separators=(",", ":"), ensure_ascii=False).encode())
        if current_chunk and current_size + span_size + overhead > max_bytes:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
        current_chunk.append(span)
        current_size += span_size

    if current_chunk:
        chunks.append(current_chunk)
    return chunks
```

#### Span truncation

If a single span exceeds 250,000 bytes (typically due to large `gen_ai.input.messages` or `gen_ai.output.messages`), truncate the largest attribute values by replacing them with `"TRUNCATED"`. Prioritize keeping structural attributes intact and truncating message content first.

### Grouping requirement

All spans in a single POST must share the same `microsoft.tenant.id` and `gen_ai.agent.id`. If your batch contains spans for multiple tenants or agents, partition them into separate requests.

### Example 3: Custom exporter for the Agent 365 backend

A minimal `SpanExporter` that builds the JSON envelope and POSTs to the A365 endpoint. This replaces the SDK's internal exporter without any A365 dependency.

```python
import json
import logging
import time
from collections.abc import Sequence

import requests
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

# Accepted operation names — spans with other values are filtered out
ACCEPTED_OPERATIONS = frozenset({
    "invoke_agent", "execute_tool", "output_messages",
    "chat", "Chat", "TextCompletion", "GenerateContent",
})

A365_ENDPOINT = "https://agent365.svc.cloud.microsoft"
MAX_PAYLOAD_BYTES = 900_000
MAX_RETRIES = 3
HTTP_TIMEOUT = 30.0


class Agent365ManualExporter(SpanExporter):
    """Minimal exporter that POSTs spans to the Agent 365 backend."""

    def __init__(self, token_resolver):
        """
        Args:
            token_resolver: Callable(agent_id, tenant_id) -> bearer_token string or None.
        """
        self._token_resolver = token_resolver
        self._session = requests.Session()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        # Partition by (tenant_id, agent_id)
        groups = self._partition(spans)
        if not groups:
            return SpanExportResult.SUCCESS

        any_failure = False
        for (tenant_id, agent_id), group_spans in groups.items():
            url = (
                f"{A365_ENDPOINT}/observability/tenants/{tenant_id}"
                f"/otlp/agents/{agent_id}/traces?api-version=1"
            )

            # Resolve auth token
            try:
                token = self._token_resolver(agent_id, tenant_id)
            except Exception as e:
                logger.error(f"Token resolution failed: {e}")
                any_failure = True
                continue

            if token is None:
                logger.warning(
                    f"Token resolver returned None for agent={agent_id}, "
                    f"tenant={tenant_id}; skipping batch"
                )
                any_failure = True
                continue

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
            }

            # Build payload and chunk if necessary
            mapped_spans = [self._map_span(sp) for sp in group_spans]
            chunks = self._chunk_by_size(mapped_spans)

            for chunk in chunks:
                payload = self._build_payload_from_mapped(group_spans[0], chunk)
                body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                if not self._post_with_retries(url, body, headers):
                    any_failure = True

        return SpanExportResult.FAILURE if any_failure else SpanExportResult.SUCCESS

    def shutdown(self):
        self._session.close()

    def _partition(
        self, spans: Sequence[ReadableSpan]
    ) -> dict[tuple[str, str], list[ReadableSpan]]:
        """Filter eligible spans and group by (tenant_id, agent_id)."""
        groups: dict[tuple[str, str], list[ReadableSpan]] = {}
        for sp in spans:
            attrs = sp.attributes or {}
            op_name = str(attrs.get("gen_ai.operation.name", ""))
            if op_name not in ACCEPTED_OPERATIONS:
                continue
            tenant = str(attrs.get("microsoft.tenant.id", ""))
            agent = str(attrs.get("gen_ai.agent.id", ""))
            if not tenant or not agent:
                continue
            groups.setdefault((tenant, agent), []).append(sp)
        return groups

    def _build_payload(self, spans: Sequence[ReadableSpan]) -> dict:
        """Build the OTLP-like JSON envelope."""
        mapped = [self._map_span(sp) for sp in spans]
        return self._build_payload_from_mapped(spans[0], mapped)

    def _build_payload_from_mapped(
        self, reference_span: ReadableSpan, mapped_spans: list[dict]
    ) -> dict:
        """Build the OTLP-like JSON envelope from pre-mapped span dicts."""
        resource_attrs = {}
        if reference_span.resource:
            resource_attrs = dict(reference_span.resource.attributes)

        # Group spans by instrumentation scope
        scope_map: dict[tuple[str, str | None], list[dict]] = {}
        for sp_dict in mapped_spans:
            # Use a default scope since mapped dicts don't carry scope info
            scope_map.setdefault(("manual", None), []).append(sp_dict)

        scope_spans = [
            {"scope": {"name": name, "version": version}, "spans": mapped}
            for (name, version), mapped in scope_map.items()
        ]

        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": resource_attrs or None},
                    "scopeSpans": scope_spans,
                }
            ]
        }

    @staticmethod
    def _chunk_by_size(
        mapped_spans: list[dict], max_bytes: int = MAX_PAYLOAD_BYTES
    ) -> list[list[dict]]:
        """Split mapped spans into chunks that fit within the payload limit."""
        chunks: list[list[dict]] = []
        current_chunk: list[dict] = []
        current_size = 0
        overhead = 200  # approximate envelope overhead

        for span in mapped_spans:
            span_size = len(
                json.dumps(span, separators=(",", ":"), ensure_ascii=False).encode()
            )
            if current_chunk and current_size + span_size + overhead > max_bytes:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            current_chunk.append(span)
            current_size += span_size

        if current_chunk:
            chunks.append(current_chunk)
        return chunks if chunks else [[]]

    @staticmethod
    def _map_span(sp: ReadableSpan) -> dict:
        """Convert a ReadableSpan to the A365 JSON format."""
        ctx = sp.context
        trace_id = f"{ctx.trace_id:032x}"
        span_id = f"{ctx.span_id:016x}"
        parent_span_id = None
        if sp.parent and sp.parent.span_id:
            parent_span_id = f"{sp.parent.span_id:016x}"

        attrs = dict(sp.attributes or {})

        # Map events
        events = None
        if sp.events:
            events = [
                {
                    "timeUnixNano": ev.timestamp,
                    "name": ev.name,
                    "attributes": dict(ev.attributes) if ev.attributes else None,
                }
                for ev in sp.events
            ]

        # Map links
        links = None
        if sp.links:
            links = [
                {
                    "traceId": f"{link.context.trace_id:032x}",
                    "spanId": f"{link.context.span_id:016x}",
                    "attributes": dict(link.attributes) if link.attributes else None,
                }
                for link in sp.links
            ]

        # Map status
        status_code = sp.status.status_code if sp.status else StatusCode.UNSET
        status = {
            "code": status_code.name,
            "message": getattr(sp.status, "description", "") or "",
        }

        return {
            "traceId": trace_id,
            "spanId": span_id,
            "parentSpanId": parent_span_id,
            "name": sp.name,
            "kind": sp.kind.name,
            "startTimeUnixNano": sp.start_time,
            "endTimeUnixNano": sp.end_time,
            "attributes": attrs or None,
            "events": events,
            "links": links,
            "status": status,
        }

    def _post_with_retries(self, url: str, body: str, headers: dict) -> bool:
        """POST with exponential backoff on transient errors."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    url, data=body, headers=headers, timeout=HTTP_TIMEOUT
                )
                if 200 <= resp.status_code < 300:
                    return True
                if resp.status_code in (408, 429) or resp.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        # Respect Retry-After for 429
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            time.sleep(min(float(retry_after), 60.0))
                        else:
                            time.sleep(0.5 * (2 ** attempt))
                        continue
                logger.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            except requests.RequestException as e:
                if attempt < MAX_RETRIES:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                logger.error(f"Request failed after {MAX_RETRIES + 1} attempts: {e}")
                return False
        return False
```

**Usage:**

```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def my_token_resolver(agent_id: str, tenant_id: str) -> str | None:
    # Your token acquisition logic here (MSAL, managed identity, etc.)
    # Return None if token cannot be acquired
    return "your-bearer-token"

exporter = Agent365ManualExporter(token_resolver=my_token_resolver)
provider.add_span_processor(BatchSpanProcessor(exporter))
```

### Example 4: End-to-end agent loop with A365 export

Combines everything: proper span hierarchy, all recommended attributes, and export to the Agent 365 backend.

```python
"""
Complete example: manually instrumented agent with A365 export.

Requirements:
    pip install opentelemetry-sdk opentelemetry-api requests

Replace the placeholder values with your actual tenant ID, agent ID,
and token resolver implementation.
"""

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
SERVICE_NAMESPACE = "my-namespace"
MODEL_NAME = "gpt-4o"
PROVIDER_NAME = "azure"
SERVER_ADDRESS = "my-resource.openai.azure.com"


def my_token_resolver(agent_id: str, tenant_id: str) -> str | None:
    """Replace with your actual token acquisition logic."""
    raise NotImplementedError("Implement your token resolver")


# --- OpenTelemetry setup ---
resource = Resource.create({
    "service.name": AGENT_NAME,
    "service.namespace": SERVICE_NAMESPACE,
})
provider = TracerProvider(resource=resource)

# For development: console export to verify spans locally
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

# For production: uncomment to export to Agent 365 backend
# from agent365_exporter import Agent365ManualExporter  # Example 3 above
# provider.add_span_processor(BatchSpanProcessor(
#     Agent365ManualExporter(token_resolver=my_token_resolver)
# ))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("my-agent-instrumentation", "1.0.0")

# --- Common attributes helper ---
COMMON_ATTRS = {
    "microsoft.tenant.id": TENANT_ID,
    "gen_ai.agent.id": AGENT_ID,
    "gen_ai.agent.name": AGENT_NAME,
    "telemetry.sdk.name": "A365ObservabilitySDK",
    "telemetry.sdk.language": "python",
    "telemetry.sdk.version": "1.0.0",
}


def set_common_attrs(span):
    for key, value in COMMON_ATTRS.items():
        span.set_attribute(key, value)


# --- Simulated tools ---
def get_weather(city: str) -> str:
    return json.dumps({"city": city, "temp_f": 62, "condition": "cloudy"})


# --- Agent turn ---
def handle_user_turn(user_message: str, user_id: str):
    session_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    with tracer.start_as_current_span(
        name=f"invoke_agent {AGENT_NAME}",
        kind=trace.SpanKind.INTERNAL,
    ) as agent_span:
        set_common_attrs(agent_span)
        agent_span.set_attribute("gen_ai.operation.name", "invoke_agent")
        agent_span.set_attribute("microsoft.session.id", session_id)
        agent_span.set_attribute("gen_ai.conversation.id", conversation_id)
        agent_span.set_attribute("user.id", user_id)
        agent_span.set_attribute("gen_ai.input.messages", json.dumps([
            {"role": "user", "content": user_message}
        ]))

        # Step 1: Call the LLM
        with tracer.start_as_current_span(
            name=f"Chat {MODEL_NAME}",
            kind=trace.SpanKind.INTERNAL,
        ) as inference_span:
            set_common_attrs(inference_span)
            inference_span.set_attribute("gen_ai.operation.name", "Chat")
            inference_span.set_attribute("gen_ai.request.model", MODEL_NAME)
            inference_span.set_attribute("gen_ai.provider.name", PROVIDER_NAME)
            inference_span.set_attribute("gen_ai.conversation.id", conversation_id)
            inference_span.set_attribute("server.address", SERVER_ADDRESS)

            # ... your LLM call here ...
            # Simulate response with tool call
            inference_span.set_attribute("gen_ai.usage.input_tokens", 55)
            inference_span.set_attribute("gen_ai.usage.output_tokens", 22)
            inference_span.set_attribute("gen_ai.response.finish_reasons", json.dumps(["tool_calls"]))

        # Step 2: Execute the tool
        tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
        tool_name = "get_weather"
        tool_args = json.dumps({"city": "Seattle"})

        with tracer.start_as_current_span(
            name=f"execute_tool {tool_name}",
            kind=trace.SpanKind.INTERNAL,
        ) as tool_span:
            set_common_attrs(tool_span)
            tool_span.set_attribute("gen_ai.operation.name", "execute_tool")
            tool_span.set_attribute("gen_ai.tool.name", tool_name)
            tool_span.set_attribute("gen_ai.tool.call.id", tool_call_id)
            tool_span.set_attribute("gen_ai.tool.call.arguments", tool_args)
            tool_span.set_attribute("gen_ai.conversation.id", conversation_id)
            tool_span.set_attribute("gen_ai.tool.type", "function")

            result = get_weather("Seattle")
            tool_span.set_attribute("gen_ai.tool.call.result", result)

        # Step 3: Final LLM call with tool result
        with tracer.start_as_current_span(
            name=f"Chat {MODEL_NAME}",
            kind=trace.SpanKind.INTERNAL,
        ) as final_inference_span:
            set_common_attrs(final_inference_span)
            final_inference_span.set_attribute("gen_ai.operation.name", "Chat")
            final_inference_span.set_attribute("gen_ai.request.model", MODEL_NAME)
            final_inference_span.set_attribute("gen_ai.provider.name", PROVIDER_NAME)
            final_inference_span.set_attribute("gen_ai.conversation.id", conversation_id)
            final_inference_span.set_attribute("server.address", SERVER_ADDRESS)

            # ... your LLM call with tool result here ...
            final_inference_span.set_attribute("gen_ai.usage.input_tokens", 85)
            final_inference_span.set_attribute("gen_ai.usage.output_tokens", 45)
            final_inference_span.set_attribute("gen_ai.response.finish_reasons", json.dumps(["stop"]))


# --- Run ---
if __name__ == "__main__":
    handle_user_turn("What's the weather in Seattle?", user_id="user-456")
    provider.force_flush()
    print("Done — check console output for spans")
```

## Validation and troubleshooting

### Verifying locally

1. Use `ConsoleSpanExporter` (shown in the examples above) to dump spans to stdout
2. Check that each span has:
   - A `gen_ai.operation.name` from the [accepted values list](#accepted-gen_aioperationname-values)
   - Both `microsoft.tenant.id` and `gen_ai.agent.id` set to non-empty strings
   - Correct parent-child relationships (`parentSpanId` on children matches root's `spanId`)

### Verifying against the backend

After switching to the `Agent365ManualExporter`:

1. **HTTP 200–299** → spans accepted. They should appear in the Agent 365 portal within a few minutes.
2. **HTTP 401/403** → token resolver returned an invalid or expired token. Check your auth implementation.
3. **HTTP 400** → payload format is wrong. Validate your JSON against the [payload format](#payload-format) section.
4. **HTTP 429** → rate limited. The exporter should respect `Retry-After` and retry automatically.
5. **No response / timeout** → check network connectivity to `agent365.svc.cloud.microsoft`.

### Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Spans don't appear in portal | `gen_ai.operation.name` not in accepted list | Use exactly `"invoke_agent"`, `"Chat"`, or `"execute_tool"` |
| Spans silently dropped | Missing `microsoft.tenant.id` or `gen_ai.agent.id` | Ensure both are set on every span |
| HTTP 400 from backend | Payload structure doesn't match expected format | Verify JSON envelope matches the documented structure |
| HTTP 401 from backend | Token resolver returns wrong/expired token | Debug your token acquisition; ensure scope matches |
| Only `invoke_agent` spans visible | Child spans missing required identity attrs | Set `microsoft.tenant.id` and `gen_ai.agent.id` on ALL spans, not just the root |
| Large spans truncated | Span exceeds 250KB | Reduce `gen_ai.input.messages` / `gen_ai.output.messages` content |

### Versioning note

This document describes the Agent 365 backend contract as of May 2026. The payload format may evolve over time. The A365 SDK (`microsoft-agents-a365-observability-core`) handles format changes automatically and is the recommended path for production workloads that can accept the dependency.

# Design: Manual Agent 365 Span Instrumentation (without the SDK)

**Date:** 2026-05-19
**Status:** Approved
**Branch:** `docs/manual-a365-span-instrumentation`

## Problem Statement

Teams with existing OpenTelemetry-instrumented Python applications want their spans to appear in the Agent 365 portal without taking a dependency on any `microsoft-agents-a365-*` package. They need a documented attribute contract and export protocol so they can manually set the right span attributes and POST to the A365 ingestion endpoint using only `opentelemetry-sdk` and `requests`.

## Audience

Python developers who:
- Already have OpenTelemetry configured (any exporter)
- Want A365 portal compatibility without importing the A365 SDK
- Need to understand the exact attribute contract the backend expects

## Deliverable

A single documentation file: `docs/manual-a365-span-instrumentation.md`

## Document Structure

| Section | Content |
|---------|---------|
| When to use this guide | Audience, prerequisites, when to use the SDK instead |
| Attribute contract | 3 tiered tables (required/recommended/optional) per span type |
| Resource attributes | What to set on the TracerProvider resource |
| SDK-identifying attributes | Optional telemetry.sdk.* attrs for identification |
| Complete examples | 3 runnable Python snippets (minimal → full → export) |
| Exporting to Agent 365 | Endpoint URL, auth, payload format, size limits, retry |
| End-to-end example | Full agent loop with proper span hierarchy + export |
| Validation & troubleshooting | Verify spans arrive; common rejection reasons |

## Attribute Contract

### Span Type: `invoke_agent`

The top-level span representing one user turn / agent invocation.

| Tier | Attribute | Expected Value |
|------|-----------|----------------|
| **Required** | `gen_ai.operation.name` | `"invoke_agent"` |
| **Required** | `microsoft.tenant.id` | Tenant GUID |
| **Required** | `gen_ai.agent.id` | Agent GUID |
| Recommended | `gen_ai.agent.name` | Human-readable agent name |
| Recommended | `microsoft.session.id` | Session identifier |
| Recommended | `gen_ai.conversation.id` | Conversation identifier |
| Recommended | `microsoft.a365.agent.blueprint.id` | Blueprint identifier |
| Recommended | `microsoft.a365.agent.platform.id` | Platform identifier |
| Recommended | `user.id` | End-user identifier |
| Recommended | `server.address` | Server hostname |
| Optional | `gen_ai.agent.description` | Agent description |
| Optional | `gen_ai.agent.version` | Agent version string |
| Optional | `microsoft.agent.user.id` | Agent's user identity |
| Optional | `microsoft.agent.user.email` | Agent's user email |
| Optional | `user.email` | End-user email |
| Optional | `user.name` | End-user display name |
| Optional | `client.address` | Client IP/hostname |
| Optional | `microsoft.channel.name` | Channel name (Teams, Webchat, etc.) |
| Optional | `microsoft.channel.link` | Channel link/URL |
| Optional | `gen_ai.input.messages` | JSON-serialized input messages |
| Optional | `microsoft.a365.caller.agent.name` | Calling agent name (agent-to-agent) |
| Optional | `microsoft.a365.caller.agent.id` | Calling agent ID (agent-to-agent) |

### Span Type: `inference` (LLM call)

Child of `invoke_agent`. One per LLM inference call.

| Tier | Attribute | Expected Value |
|------|-----------|----------------|
| **Required** | `gen_ai.operation.name` | `"Chat"` (or `"TextCompletion"` / `"GenerateContent"`) |
| **Required** | `microsoft.tenant.id` | Tenant GUID |
| **Required** | `gen_ai.agent.id` | Agent GUID |
| **Required** | `gen_ai.request.model` | Model name (e.g. `"gpt-4o"`) |
| Recommended | `gen_ai.usage.input_tokens` | Integer token count |
| Recommended | `gen_ai.usage.output_tokens` | Integer token count |
| Recommended | `gen_ai.response.finish_reasons` | JSON array of finish reasons |
| Recommended | `gen_ai.conversation.id` | Conversation identifier |
| Recommended | `gen_ai.provider.name` | Provider (e.g. `"openai"`, `"azure"`) |
| Optional | `gen_ai.input.messages` | JSON-serialized input messages |
| Optional | `gen_ai.output.messages` | JSON-serialized output messages |
| Optional | `server.address` | LLM endpoint hostname |
| Optional | `server.port` | LLM endpoint port (omit if 443) |
| Optional | `microsoft.a365.agent.thought.process` | Agent reasoning trace |

### Span Type: `execute_tool`

Child of `invoke_agent`. One per tool invocation.

| Tier | Attribute | Expected Value |
|------|-----------|----------------|
| **Required** | `gen_ai.operation.name` | `"execute_tool"` |
| **Required** | `microsoft.tenant.id` | Tenant GUID |
| **Required** | `gen_ai.agent.id` | Agent GUID |
| **Required** | `gen_ai.tool.name` | Tool function name |
| Recommended | `gen_ai.tool.call.id` | Tool call ID from LLM response |
| Recommended | `gen_ai.tool.call.arguments` | JSON-serialized arguments |
| Recommended | `gen_ai.tool.call.result` | JSON-serialized result |
| Recommended | `gen_ai.conversation.id` | Conversation identifier |
| Optional | `gen_ai.tool.type` | Tool type (e.g. `"function"`) |
| Optional | `gen_ai.tool.description` | Tool description |
| Optional | `server.address` | Server hostname |

### Resource Attributes (on TracerProvider)

| Tier | Attribute | Expected Value |
|------|-----------|----------------|
| **Required** | `service.name` | Your service/agent name |
| Recommended | `service.namespace` | Your service namespace |

### SDK-Identifying Attributes (on all spans)

These are optional but help the backend identify the telemetry source:

| Attribute | Value |
|-----------|-------|
| `telemetry.sdk.name` | `"A365ObservabilitySDK"` (or your own identifier) |
| `telemetry.sdk.language` | `"python"` |
| `telemetry.sdk.version` | Your version string |

## Export Protocol

### Endpoint

```
POST https://agent365.svc.cloud.microsoft/observability/tenants/{tenantId}/otlp/agents/{agentId}/traces?api-version=1
```

Where `{tenantId}` and `{agentId}` come from the span attributes `microsoft.tenant.id` and `gen_ai.agent.id`.

### Authentication

```
Authorization: Bearer <token>
Content-Type: application/json
```

Token is obtained from a resolver function with signature: `(agent_id: str, tenant_id: str) -> str`

The guide will document the interface but not prescribe a specific token acquisition method (MSAL, managed identity, etc.) since that depends on the deployment environment.

### Payload Format

OTLP-like JSON (not standard OTLP protobuf):

```json
{
  "resourceSpans": [
    {
      "resource": {
        "attributes": { "service.name": "my-agent", "service.namespace": "my-ns" }
      },
      "scopeSpans": [
        {
          "scope": { "name": "my-instrumentor", "version": "1.0.0" },
          "spans": [
            {
              "traceId": "0af7651916cd43dd8448eb211c80319c",
              "spanId": "b7ad6b7169203331",
              "parentSpanId": null,
              "name": "invoke_agent my-agent",
              "kind": "INTERNAL",
              "startTimeUnixNano": 1716000000000000000,
              "endTimeUnixNano": 1716000001000000000,
              "attributes": { "gen_ai.operation.name": "invoke_agent", "..." : "..." },
              "events": null,
              "links": null,
              "status": { "code": "OK", "message": "" }
            }
          ]
        }
      ]
    }
  ]
}
```

### Constraints

| Constraint | Value | Behavior on violation |
|------------|-------|----------------------|
| Max payload size | ~900,000 bytes | Split into multiple POSTs (chunks) |
| Max individual span size | 250,000 bytes | Largest attributes truncated to `"TRUNCATED"` |
| Required span filter | `gen_ai.operation.name` ∈ `{invoke_agent, execute_tool, chat, Chat}` | Spans with other values are silently dropped |
| Required identity | Both `microsoft.tenant.id` and `gen_ai.agent.id` present and non-empty | Spans without both are silently dropped |
| Retryable HTTP codes | 408, 429, 5xx | Retry with exponential backoff (respect `Retry-After` for 429) |
| Non-retryable HTTP codes | Other 4xx | Fail immediately |

### Span Name Convention

| Span type | Span name format |
|-----------|-----------------|
| invoke_agent | `"invoke_agent"` or `"invoke_agent <agent_name>"` |
| inference | `"<operation> <model>"` (e.g. `"Chat gpt-4o"`) |
| execute_tool | `"execute_tool <tool_name>"` |

## Examples Plan

### Example 1: Minimal invoke_agent span

Creates a single root span with only required attributes, exports to `ConsoleSpanExporter` for verification.

### Example 2: Full agent turn with hierarchy

Creates `invoke_agent` → `inference` + `execute_tool` children with all recommended attributes. Still uses console export.

### Example 3: DIY export to Agent 365 backend

Implements a minimal custom `SpanExporter` that builds the JSON envelope and POSTs to the A365 endpoint with Bearer auth. Shows the complete flow from span creation to backend ingestion without any A365 package.

### Example 4: End-to-end agent loop

Combines examples 2 + 3 into a realistic agent loop: receive user message → invoke_agent span → call OpenAI (inference span) → execute tool (execute_tool span) → export to A365.

## Validation & Troubleshooting

The guide will include:
- How to verify spans appear in the A365 portal after export
- Common HTTP error codes and what they mean
- Checklist: "My spans aren't showing up" (missing required attrs, wrong operation name, auth failure, payload too large)

## Key Design Decisions

1. **Zero A365 package dependency** — only `opentelemetry-sdk` and `requests` required
2. **Tiered attribute contract** — Required (backend drops without) / Recommended (enables features) / Optional (enrichment)
3. **Document the allow-list explicitly** — spans with `gen_ai.operation.name` not in the set are filtered
4. **Token resolver interface documented, not implementation** — users bring their own auth
5. **Custom exporter example, not OTLPSpanExporter** — A365 backend uses a custom JSON format, not standard OTLP
6. **Versioning caveat** — the guide will note that the payload format is a contract that may evolve; the SDK handles this automatically and is the recommended path for production

## Out of Scope

- Token acquisition implementation (MSAL, managed identity, etc.)
- Multi-language support (future work)
- Baggage propagation (SDK-specific concern, not needed for manual spans)
- The `_EnrichingBatchSpanProcessor` enrichment pattern (SDK internal)

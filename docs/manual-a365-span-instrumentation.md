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

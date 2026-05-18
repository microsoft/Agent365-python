# Integrating with existing OpenTelemetry

This guide is for developers whose application **already** initializes OpenTelemetry — for example with `azure-monitor-opentelemetry`, an OTLP collector, or a vendor-specific exporter — and who want Agent 365 spans to flow alongside their existing telemetry. If you're starting fresh, see the [observability-core README](../libraries/microsoft-agents-a365-observability-core/README.md) for the standalone setup.

## The integration rule

> **Initialize your existing OpenTelemetry stack first, then call Agent 365's `configure()`.** The SDK detects the existing `TracerProvider` and adds its processors to it. Your existing backend receives every span; the Agent 365 backend also receives spans when `ENABLE_A365_OBSERVABILITY_EXPORTER=true` and a `token_resolver` is provided (otherwise `configure()` falls back to `ConsoleSpanExporter`).

The detection happens in [`config.py`](../libraries/microsoft-agents-a365-observability-core/microsoft_agents_a365/observability/core/config.py): if a real (non-no-op) `TracerProvider` is already set (detected via a non-None `resource` attribute), `configure()` adds an `_EnrichingBatchSpanProcessor` (wrapping the configured exporter) and a custom `SpanProcessor` to that provider rather than creating a new one.

## Two minimal patterns

### Pattern A — `azure-monitor-opentelemetry`

```python
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from microsoft_agents_a365.observability.core import configure

# 1. Existing OTel: Azure Monitor sets up a TracerProvider + AM exporter.
configure_azure_monitor(connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"])

# 2. Agent 365 attaches its processors to that same TracerProvider.
configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    token_resolver=my_token_resolver,
)
```

→ Runnable version: [`observability-with-azure-monitor`](https://github.com/microsoft/Agent365-Samples/tree/main/python/observability-with-azure-monitor) sample.

### Pattern B — manual OTel SDK + OTLP exporter

```python
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from microsoft_agents_a365.observability.core import configure

# 1. Existing OTel: build provider + OTLP exporter explicitly.
provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "my-agent"}))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]))
)
trace.set_tracer_provider(provider)

# 2. Agent 365 attaches to that same provider.
configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    token_resolver=my_token_resolver,
)
```

→ Runnable version: [`observability-with-otlp`](https://github.com/microsoft/Agent365-Samples/tree/main/python/observability-with-otlp) sample (defaults to `ConsoleSpanExporter` for zero setup).

## Auto-instrumentation vs. manual instrumentation

The OTel **backend** (where spans go) and the **instrumentation style** (how spans are produced) are independent axes. You can mix them freely.

|                          | Auto (extension package)                                          | Manual (`InvokeAgentScope` / `InferenceScope` / `ExecuteToolScope`) |
|--------------------------|-------------------------------------------------------------------|--------------------------------------------------------------------|
| **Azure Monitor**        | Demonstrated by `observability-with-azure-monitor` sample         | Same `configure()`; replace agent code with manual scope wrapping  |
| **OTLP / vendor-neutral** | Same `configure()`; install your framework's extension package   | Demonstrated by `observability-with-otlp` sample                   |

For auto-instrumentation, install the framework-specific extension package — for example:

- OpenAI Agents SDK → `microsoft-agents-a365-observability-extensions-openai`
- LangChain → `microsoft-agents-a365-observability-extensions-langchain`
- Semantic Kernel → `microsoft-agents-a365-observability-extensions-semantickernel`
- Microsoft Agent Framework → `microsoft-agents-a365-observability-extensions-agentframework`

For the OpenAI Agents SDK extension, instantiate `OpenAIAgentsTraceInstrumentor()` and call `.instrument()` **after** `configure()`. The instrumentor raises `RuntimeError` if Agent 365 isn't configured first.

## What spans should I expect to see?

The SDK produces three core span kinds. Your backend should show them in this typical hierarchy:

| `gen_ai.operation.name` | Produced by                                       | Typical parent | Span name (default) | Notes |
|-------------------------|---------------------------------------------------|----------------|---------------------|-------|
| `invoke_agent`          | `InvokeAgentScope` (one per user turn)            | (root or app)  | `invoke_agent <agent_name>` when set, else `invoke_agent` | |
| (varies — see notes) | `InferenceScope` (one per LLM call) | `invoke_agent` | `<operation> <model>` | **Manual instrumentation** uses `InferenceOperationType.value` (currently `Chat` / `TextCompletion` / `GenerateContent`, capitalized). **Auto-instrumentation** (e.g. `OpenAIAgentsTraceInstrumentor`) uses lowercase per the [OTel GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) (e.g. `chat`). The two are inconsistent today. |
| `execute_tool`          | `ExecuteToolScope` (one per tool invocation)      | `invoke_agent` | `execute_tool <tool_name>` (always includes the tool name) | Records tool name, args, and result. |

Filter your backend by the `gen_ai.operation.name` attribute or by span name. Note that `inference` is *not* the literal attribute value — manual instrumentation produces `Chat` / `TextCompletion` / `GenerateContent` (the `InferenceOperationType.value`), while auto-instrumentation extension packages produce the lowercase OTel-spec form (e.g. `chat`). This casing discrepancy is tracked as an SDK issue.

## Verifying the integration

If you've called `configure()` but don't see Agent 365 spans in your backend, isolate the problem by adding a `ConsoleSpanExporter` temporarily:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# After configure() has run:
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
```

Run a single turn. If you see `invoke_agent` / `Chat` (or `chat`) / `execute_tool` JSON dumps on stdout, the SDK is producing spans correctly — the issue is in your backend exporter (network, auth, sampling). If you don't see them, the integration itself is wrong; check the pitfalls below.

## Common pitfalls

### Pitfall 1: Calling `configure_azure_monitor()` after Agent 365 `configure()`

**Symptom:** Agent 365 spans don't appear in any backend.

**Cause:** `configure_azure_monitor` (and many vendor packages) replace the global `TracerProvider`. If they run *after* `configure()`, the provider with our processors is discarded.

**Fix:** Always initialize Azure Monitor (or any OTel setup) **before** calling Agent 365 `configure()`.

### Pitfall 2: Calling Agent 365 `configure()` before app's OTel setup

**Symptom:** Same as above — Agent 365 spans are missing.

**Cause:** `configure()` creates its own `TracerProvider` (no existing one detected). Your app's later OTel init replaces it, dropping our processors.

**Fix:** Same as Pitfall 1 — OTel first, then Agent 365.

### Pitfall 3: `OTEL_SDK_DISABLED=true` or `OTEL_TRACES_EXPORTER=none`

**Symptom:** Nothing exports — neither your existing backend nor Agent 365.

**Cause:** These environment variables disable OpenTelemetry SDK-wide. They suppress Agent 365 spans alongside everything else.

**Fix:** Use sampling (`OTEL_TRACES_SAMPLER`) or per-exporter configuration instead of the global disable. If you intentionally want to disable tracing in a particular environment, that's fine — just understand it disables Agent 365 too.

### Pitfall 4: `ENABLE_OBSERVABILITY` not set

**Symptom:** Your existing OTel backend works (Azure Monitor / OTLP / etc. show spans), but Agent 365 scope blocks (`InvokeAgentScope`, `InferenceScope`, `ExecuteToolScope`) produce zero spans. No errors, no warnings.

**Cause:** Agent 365's scope classes gate span creation on the `ENABLE_OBSERVABILITY` (or `ENABLE_A365_OBSERVABILITY`) environment variable. If neither is set to `true` / `1` / `yes` / `on`, every scope's `__init__` skips span creation entirely. This is **independent** of OTel's own enable/disable mechanism — your existing OTel telemetry continues to flow normally.

**Fix:** Set `ENABLE_OBSERVABILITY=true` (or `ENABLE_A365_OBSERVABILITY=true`) in your environment before creating any scopes / emitting spans (the check happens at scope construction time, not import time). Both runnable samples include this in their `.env.template`.

## Exporter combinations

| Combination                             | What's installed                                                          | What to call                                                              | Gotchas                                                                                       |
|-----------------------------------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Azure Monitor only                      | `azure-monitor-opentelemetry`                                             | `configure_azure_monitor(...)`                                            | Standard Azure Monitor — no Agent 365 spans flow.                                             |
| Azure Monitor + Agent 365               | `azure-monitor-opentelemetry`, `microsoft-agents-a365-observability-core` | `configure_azure_monitor(...)` then `configure(...)`                      | Order matters (see Pitfall 1).                                                                |
| OTLP collector + Agent 365              | `opentelemetry-sdk`, `opentelemetry-exporter-otlp-*`, A365 core           | Build provider + `BatchSpanProcessor(OTLPSpanExporter(...))` then `configure(...)` | Set `OTEL_EXPORTER_OTLP_ENDPOINT`; collector must be reachable.                          |
| Agent 365 only                          | `microsoft-agents-a365-observability-core`                                | `configure(...)` only                                                     | SDK creates its own `TracerProvider`; spans go to Agent 365 backend only.                     |
| OTLP + Azure Monitor + Agent 365        | All of the above                                                          | Configure Azure Monitor first; add OTLP `BatchSpanProcessor` to the provider; call `configure(...)` | All three exporters receive every span. Watch out for duplicate processors if Azure Monitor itself adds OTLP. |

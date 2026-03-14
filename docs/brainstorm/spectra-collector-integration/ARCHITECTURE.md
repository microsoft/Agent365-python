# Spectra Collector Integration — Architecture Proposal

**Date:** 2026-03-14
**Status:** Ready to build

---

## Overview

Integrate Spectra Collector as an optional export destination in the `microsoft-agents-a365-observability-core` package. Consumers deploying with Spectra sidecars in K8s pass `SpectraExporterOptions` to `configure()` instead of `Agent365ExporterOptions`. Under the hood, this creates an `OTLPSpanExporter` pointed at the Spectra sidecar.

---

## Architecture

### Exporter Selection Flow (after change)

```
configure(exporter_options=SpectraExporterOptions(...))
    │
    ├─ if isinstance(exporter_options, SpectraExporterOptions):
    │     → OTLPSpanExporter(endpoint, protocol, insecure)
    │     → ENABLE_A365_OBSERVABILITY_EXPORTER env var is IGNORED
    │
    ├─ elif isinstance(exporter_options, Agent365ExporterOptions):
    │     → if ENABLE_A365_OBSERVABILITY_EXPORTER + token_resolver:
    │     │     → _Agent365Exporter (custom HTTP)
    │     → else:
    │           → ConsoleSpanExporter (fallback)
    │
    └─ if ENABLE_OTLP_EXPORTER=true:  (unchanged, additive)
          → OTLPSpanExporter (auto-configured from OTEL env vars)
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Consumer Application                                       │
│                                                             │
│  configure(exporter_options=SpectraExporterOptions())       │
│      or                                                     │
│  configure(exporter_options=Agent365ExporterOptions(...))   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  TelemetryManager._configure_internal()                     │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐    │
│  │ SpectraExporterOpts │    │ Agent365ExporterOptions  │    │
│  │ endpoint (4317)     │    │ token_resolver           │    │
│  │ protocol (gRPC)     │    │ cluster_category         │    │
│  │ insecure (true)     │    │ use_s2s_endpoint         │    │
│  │ batch settings      │    │ batch settings           │    │
│  └────────┬────────────┘    └────────┬────────────────┘    │
│           │                          │                      │
│           ▼                          ▼                      │
│  ┌─────────────────┐       ┌──────────────────┐           │
│  │ OTLPSpanExporter│       │ _Agent365Exporter│           │
│  │ (standard OTEL) │       │ (custom HTTP)    │           │
│  └────────┬────────┘       └────────┬─────────┘           │
│           │                          │                      │
│           └──────────┬───────────────┘                      │
│                      ▼                                      │
│           ┌──────────────────────────┐                      │
│           │ _EnrichingBatchSpan-     │                      │
│           │ Processor                │  ← enrichers from    │
│           │ (exporter-agnostic)      │    framework exts    │
│           └──────────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   Spectra Sidecar            A365 API
   (localhost:4317)           (agent365.svc.cloud.microsoft)
```

---

## New File: `spectra_exporter_options.py`

Location: `libraries/microsoft-agents-a365-observability-core/microsoft_agents_a365/observability/core/exporters/spectra_exporter_options.py`

```python
class SpectraExporterOptions:
    """
    Configuration for exporting traces to a Spectra Collector sidecar via OTLP.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        protocol: str = "grpc",
        insecure: bool = True,
        max_queue_size: int = 2048,
        scheduled_delay_ms: int = 5000,
        exporter_timeout_ms: int = 30000,
        max_export_batch_size: int = 512,
    ):
        self.endpoint = endpoint
        self.protocol = protocol          # "grpc" or "http"
        self.insecure = insecure
        self.max_queue_size = max_queue_size
        self.scheduled_delay_ms = scheduled_delay_ms
        self.exporter_timeout_ms = exporter_timeout_ms
        self.max_export_batch_size = max_export_batch_size
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `endpoint` | `str` | `http://localhost:4317` | Spectra sidecar OTLP endpoint |
| `protocol` | `str` | `grpc` | OTLP protocol: `"grpc"` or `"http"` |
| `insecure` | `bool` | `True` | Whether to use insecure (no TLS) connection |
| `max_queue_size` | `int` | `2048` | Batch processor queue size |
| `scheduled_delay_ms` | `int` | `5000` | Export interval (ms) |
| `exporter_timeout_ms` | `int` | `30000` | Export timeout (ms) |
| `max_export_batch_size` | `int` | `512` | Max spans per export batch |

---

## Changes to `config.py`

### `configure()` signature

```python
def configure(
    service_name: str,
    service_namespace: str,
    logger_name: str = DEFAULT_LOGGER_NAME,
    token_resolver: Callable[[str, str], str | None] | None = None,
    cluster_category: str = "prod",
    exporter_options: Agent365ExporterOptions | SpectraExporterOptions | None = None,
    suppress_invoke_agent_input: bool = False,
    **kwargs: Any,
) -> bool:
```

### `_configure_internal()` exporter selection

```python
# Type-based dispatch
if isinstance(exporter_options, SpectraExporterOptions):
    # Spectra path — OTLP exporter to sidecar
    # ENABLE_A365_OBSERVABILITY_EXPORTER is ignored
    if exporter_options.protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter
        exporter = GrpcExporter(
            endpoint=exporter_options.endpoint,
            insecure=exporter_options.insecure,
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter
        exporter = HttpExporter(
            endpoint=exporter_options.endpoint,
        )

elif isinstance(exporter_options, Agent365ExporterOptions):
    # A365 path (existing logic, unchanged)
    if is_agent365_exporter_enabled() and exporter_options.token_resolver is not None:
        exporter = _Agent365Exporter(...)
    else:
        exporter = ConsoleSpanExporter()

else:
    # No options provided — legacy fallback
    exporter_options = Agent365ExporterOptions(
        cluster_category=cluster_category,
        token_resolver=token_resolver,
    )
    # ... existing logic
```

---

## Export Surface Changes

### `exporters/__init__.py`

```python
from .agent365_exporter_options import Agent365ExporterOptions
from .spectra_exporter_options import SpectraExporterOptions

__all__ = ["Agent365ExporterOptions", "SpectraExporterOptions"]
```

### `core/__init__.py`

Add `SpectraExporterOptions` to imports and `__all__`.

---

## Consumer Usage

### Spectra deployment (Weave/Copilot Cowork)

```python
from microsoft_agents_a365.observability.core import configure, SpectraExporterOptions

# Zero-config — defaults to localhost:4317, gRPC
configure(
    service_name="weave-agent",
    service_namespace="copilot-cowork",
    exporter_options=SpectraExporterOptions(),
)
```

### A365 deployment (existing consumers, unchanged)

```python
from microsoft_agents_a365.observability.core import configure, Agent365ExporterOptions

configure(
    service_name="my-agent",
    service_namespace="my-namespace",
    exporter_options=Agent365ExporterOptions(
        token_resolver=my_token_resolver,
        cluster_category="prod",
    ),
)
```

---

## Files Changed

| File | Change |
|------|--------|
| `exporters/spectra_exporter_options.py` | **New** — `SpectraExporterOptions` class |
| `exporters/__init__.py` | Add `SpectraExporterOptions` export |
| `core/__init__.py` | Add `SpectraExporterOptions` to `__all__` |
| `config.py` | Union type on `exporter_options`, type-based dispatch in `_configure_internal()` |
| `tests/observability/core/test_spectra_exporter.py` | **New** — tests for Spectra exporter path (mocked `OTLPSpanExporter`) |

## Files NOT Changed

- Scope classes (`invoke_agent_scope.py`, `execute_tool_scope.py`, etc.)
- Enrichment pipeline (`enriching_span_processor.py`)
- Framework extensions (all `*-observability-extensions-*` packages)
- Constants (`constants.py`)
- `Agent365ExporterOptions` class
- `_Agent365Exporter` class

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Sidecar not running → silent failure | Medium | OTLP exporter logs connection errors; document deployment prereqs |
| Consumer passes both A365 env var + Spectra options | Low | Spectra options take precedence; env var ignored. Document. |
| gRPC dependency not installed | Low | `opentelemetry-exporter-otlp` (core dep) includes both gRPC and HTTP |
| Consumer sets `insecure=False` for remote Spectra endpoint but forgets TLS setup | Low | Only relevant for non-sidecar deployments. Default `insecure=True` is correct for localhost. |

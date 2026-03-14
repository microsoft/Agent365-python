# Design: Spectra Collector Exporter Integration

**Author:** Agent365 SDK Team
**Date:** 2026-03-14
**Status:** Reviewed
**Brainstorm:** [docs/brainstorm/spectra-collector-integration/](../brainstorm/spectra-collector-integration/)

---

## 1. Problem Statement

The Weave/Copilot Cowork team deploys with Spectra Collector sidecars in Kubernetes and needs to export traces to the Spectra sidecar instead of the A365 observability API. Today, the `configure()` function in `observability-core` only supports `Agent365ExporterOptions`, which creates an `_Agent365Exporter` that POSTs to the A365 API with custom HTTP semantics (identity partitioning, token resolution, etc.).

There is an existing `ENABLE_OTLP_EXPORTER` env var path (`config.py:187-192`) that creates a bare `OTLPSpanExporter`, but it has no configuration surface and is designed as a generic bolt-on, not a Spectra-aware integration.

**Evidence:**
- `config.py:54-63` — `configure()` signature accepts only `Agent365ExporterOptions`
- `config.py:159-171` — exporter selection is hardcoded: A365 or console fallback
- `config.py:187-192` — OTLP bolt-on with zero configuration
- Spectra Collector accepts standard OTLP on `localhost:4317` (gRPC) / `localhost:4318` (HTTP) — confirmed from `D:\spectra-collector`

---

## 2. Current Architecture

### Affected Files Inventory

| File | Path (relative to observability-core package root) | Role | Changes |
|------|------|------|---------|
| `config.py` | `microsoft_agents_a365/observability/core/config.py` | TelemetryManager singleton, `configure()` entry point | Modify |
| `agent365_exporter_options.py` | `microsoft_agents_a365/observability/core/exporters/agent365_exporter_options.py` | A365 exporter config | No change |
| `agent365_exporter.py` | `microsoft_agents_a365/observability/core/exporters/agent365_exporter.py` | A365 exporter — remove suppression logic from `_map_span` | Modify |
| `enriching_span_processor.py` | `microsoft_agents_a365/observability/core/exporters/enriching_span_processor.py` | Batch processor — add suppression logic to `on_end` | Modify |
| `enriched_span.py` | `microsoft_agents_a365/observability/core/exporters/enriched_span.py` | Enriched span wrapper — add `excluded_attribute_keys` support | Modify |
| `exporters/__init__.py` | `microsoft_agents_a365/observability/core/exporters/__init__.py` | Exporter public exports | Modify |
| `core/__init__.py` | `microsoft_agents_a365/observability/core/__init__.py` | Package public API | Modify |
| `spectra_exporter_options.py` | `microsoft_agents_a365/observability/core/exporters/spectra_exporter_options.py` | **New** — Spectra config | Create |
| `test_spectra_exporter.py` | `tests/observability/core/test_spectra_exporter.py` | **New** — Spectra tests | Create |
| `test_agent365.py` | `tests/observability/core/test_agent365.py` | Existing config tests | Modify (add Spectra tests) |

### Current Exporter Selection (`config.py:144-192`)

```python
# Lines 144-149: Legacy fallback
if exporter_options is None:
    exporter_options = Agent365ExporterOptions(
        cluster_category=cluster_category,
        token_resolver=token_resolver,
    )

# Lines 159-171: A365 or console
if is_agent365_exporter_enabled() and exporter_options.token_resolver is not None:
    exporter = _Agent365Exporter(...)
else:
    exporter = ConsoleSpanExporter()

# Lines 187-192: Optional OTLP bolt-on
if os.environ.get("ENABLE_OTLP_EXPORTER", "").lower() == "true":
    otlp_exporter = OTLPSpanExporter()
    tracer_provider.add_span_processor(
        _EnrichingBatchSpanProcessor(otlp_exporter, **batch_processor_kwargs)
    )
```

### Unchanged Components

These components are independent of the export destination and require **zero changes**:
- Scope classes: `InvokeAgentScope`, `ExecuteToolScope`, `InferenceScope`
- Span processor: `SpanProcessor` (copies baggage to span attributes)
- All framework extension packages (`*-observability-extensions-*`)
- Constants (`constants.py`)
- `Agent365ExporterOptions` class

### Components Requiring Modification for `suppress_invoke_agent_input`

The `suppress_invoke_agent_input` feature currently lives inside `_Agent365Exporter._map_span()` (`agent365_exporter.py:274-284`), where it strips `gen_ai.input.messages` from InvokeAgent spans during JSON serialization. This is exporter-specific — the `OTLPSpanExporter` never calls `_map_span`, so suppression would be lost in the Spectra path.

**This must be moved to an exporter-agnostic layer** so it works with both A365 and Spectra exporters. See Section 5.4 for the approach.

---

## 3. Requirements

### Must-Have

| ID | Requirement |
|----|------------|
| M1 | Consumer can pass `SpectraExporterOptions` to `configure()` to export traces via OTLP to a Spectra sidecar |
| M2 | Default endpoint is `http://localhost:4317` with gRPC protocol — zero-config for K8s sidecar |
| M3 | When `SpectraExporterOptions` is provided, `ENABLE_A365_OBSERVABILITY_EXPORTER` env var is ignored entirely |
| M4 | Span enrichment pipeline works identically regardless of which exporter is active |
| M5 | No new package dependencies — `opentelemetry-exporter-otlp` is already a core dep |
| M6 | `SpectraExporterOptions` is exported from `microsoft_agents_a365.observability.core` |

### Nice-to-Have

| ID | Requirement |
|----|------------|
| N1 | Protocol field (`"grpc"` or `"http"`) for consumers who need HTTP/protobuf instead of gRPC |
| N2 | `insecure` field for TLS configuration (defaults to `True` for localhost sidecar) |

### Constraints

| ID | Constraint |
|----|-----------|
| C1 | `Agent365ExporterOptions` class and its API must not change |
| C2 | Existing consumers using `Agent365ExporterOptions` must see zero behavioral change |
| C3 | `ENABLE_OTLP_EXPORTER` bolt-on path remains separate and unchanged |
| C4 | No shared base class between `Agent365ExporterOptions` and `SpectraExporterOptions` (decided in brainstorm) |

---

## 4. Options Evaluation

### Option A: Type-based dispatch with union parameter (Recommended)

`configure()` accepts `exporter_options: Agent365ExporterOptions | SpectraExporterOptions | None`. The `_configure_internal()` method uses `isinstance` to select the exporter.

**Pros:** Explicit, type-safe, no env var ambiguity, consumer controls exporter in code
**Cons:** Union type is slightly more complex than a single type

### Option B: Separate `spectra_exporter_options` parameter

Add a new keyword arg `spectra_exporter_options: SpectraExporterOptions | None` alongside the existing `exporter_options`.

**Pros:** No type change on existing parameter
**Cons:** Two params for the same concept, awkward if both are passed, more args on an already-long signature

### Option C: Env-var-driven selection

New `ENABLE_SPECTRA_EXPORTER` env var. Consumer sets env vars instead of passing options in code.

**Pros:** Consistent with existing `ENABLE_A365_OBSERVABILITY_EXPORTER` pattern
**Cons:** Two env vars could conflict, harder to reason about, no type safety

### Comparison Matrix

| Criterion | Option A (Union) | Option B (Separate param) | Option C (Env var) |
|-----------|-----------------|--------------------------|-------------------|
| Type safety | High | Medium (mutual exclusion not enforced at type level) | Low |
| Backward compat | Full | Full | Full |
| Consumer clarity | High — one param, one choice | Medium — which param do I use? | Low — env var precedence unclear |
| Implementation complexity | Low | Low | Medium (precedence logic) |

**Decision: Option A** — confirmed in brainstorm with stakeholder input.

---

## 5. Recommended Approach

### 5.1 New File: `spectra_exporter_options.py`

**Location:** `libraries/microsoft-agents-a365-observability-core/microsoft_agents_a365/observability/core/exporters/spectra_exporter_options.py`

**Estimated size:** ~40 lines

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal


class SpectraExporterOptions:
    """
    Configuration for exporting traces to a Spectra Collector sidecar via OTLP.

    Spectra Collector is deployed as a Kubernetes sidecar that accepts
    standard OTLP telemetry on localhost. Defaults are tuned for this
    deployment topology — most consumers should not need to override them.

    Note: Batch processor fields (max_queue_size, scheduled_delay_ms, etc.)
    are duplicated from Agent365ExporterOptions intentionally — these two
    options classes have no shared base class per design decision C4.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        protocol: Literal["grpc", "http"] = "grpc",
        insecure: bool = True,
        max_queue_size: int = 2048,
        scheduled_delay_ms: int = 5000,
        exporter_timeout_ms: int = 30000,
        max_export_batch_size: int = 512,
    ):
        """
        Args:
            endpoint: Spectra sidecar OTLP endpoint. Default: http://localhost:4317.
            protocol: OTLP protocol — "grpc" or "http". Default: grpc.
            insecure: Use insecure (no TLS) connection. Default: True (localhost sidecar).
            max_queue_size: Batch processor queue size. Default: 2048.
            scheduled_delay_ms: Export interval in milliseconds. Default: 5000.
            exporter_timeout_ms: Export timeout in milliseconds. Default: 30000.
            max_export_batch_size: Max spans per export batch. Default: 512.
        """
        if protocol not in ("grpc", "http"):
            raise ValueError(
                f"protocol must be 'grpc' or 'http', got '{protocol}'"
            )
        self.endpoint = endpoint
        self.protocol = protocol
        self.insecure = insecure
        self.max_queue_size = max_queue_size
        self.scheduled_delay_ms = scheduled_delay_ms
        self.exporter_timeout_ms = exporter_timeout_ms
        self.max_export_batch_size = max_export_batch_size
```

### 5.2 Changes to `config.py`

#### Import additions (module level in `config.py`)

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GrpcOTLPSpanExporter,
)
from .exporters.spectra_exporter_options import SpectraExporterOptions
```

The gRPC exporter is imported at module level (matching the existing HTTP `OTLPSpanExporter` import at `config.py:11`). The `opentelemetry-exporter-otlp` core dependency pulls in both gRPC and HTTP sub-packages transitively, so the import is safe. This also provides a clean mock target for tests: `@patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")`.

#### Signature change — all three functions

The `exporter_options` parameter type changes on **all three** function signatures that must stay in sync:

1. Public `configure()` at `config.py:245`
2. `TelemetryManager.configure()` at `config.py:54`
3. `TelemetryManager._configure_internal()` at `config.py:96`

From:
```python
exporter_options: Optional[Agent365ExporterOptions] = None
```
To:
```python
exporter_options: Agent365ExporterOptions | SpectraExporterOptions | None = None
```

#### Exporter selection in `_configure_internal()` (replaces lines 144-171)

The existing early-resolve pattern is preserved — `None` resolves to `Agent365ExporterOptions` first, then `batch_processor_kwargs` are extracted once, then `isinstance` dispatch:

```python
# Resolve None to default Agent365ExporterOptions (legacy fallback)
if exporter_options is None:
    exporter_options = Agent365ExporterOptions(
        cluster_category=cluster_category,
        token_resolver=token_resolver,
    )

# Extract batch processor kwargs — works for both options types
# (both have identical field names: max_queue_size, scheduled_delay_ms, etc.)
batch_processor_kwargs = {
    "max_queue_size": exporter_options.max_queue_size,
    "schedule_delay_millis": exporter_options.scheduled_delay_ms,
    "export_timeout_millis": exporter_options.exporter_timeout_ms,
    "max_export_batch_size": exporter_options.max_export_batch_size,
}

# Type-based exporter dispatch
if isinstance(exporter_options, SpectraExporterOptions):
    # Spectra path — OTLP exporter to sidecar
    # ENABLE_A365_OBSERVABILITY_EXPORTER is intentionally ignored.
    # suppress_invoke_agent_input is handled by _EnrichingBatchSpanProcessor
    # (see Section 5.3), so it works with both A365 and Spectra exporters.
    if exporter_options.protocol == "grpc":
        exporter = GrpcOTLPSpanExporter(
            endpoint=exporter_options.endpoint,
            insecure=exporter_options.insecure,
        )
    else:
        exporter = OTLPSpanExporter(
            endpoint=exporter_options.endpoint,
        )

else:
    # A365 path (existing logic, unchanged)
    if is_agent365_exporter_enabled() and exporter_options.token_resolver is not None:
        exporter = _Agent365Exporter(
            token_resolver=exporter_options.token_resolver,
            cluster_category=exporter_options.cluster_category,
            use_s2s_endpoint=exporter_options.use_s2s_endpoint,
        )
    else:
        exporter = ConsoleSpanExporter()
```

**Design notes:**
- `None` resolves to `Agent365ExporterOptions` early, preserving the existing single-path pattern and eliminating code duplication.
- `batch_processor_kwargs` are extracted once — both options classes share identical field names and defaults.
- `suppress_invoke_agent_input` is moved from `_Agent365Exporter._map_span()` to `_EnrichingBatchSpanProcessor.on_end()` so it works with any exporter (see Section 5.3). The flag is passed to the batch processor, not the exporter.

### 5.3 Moving `suppress_invoke_agent_input` to the enrichment layer

Currently, input message suppression lives inside `_Agent365Exporter._map_span()` (`agent365_exporter.py:274-284`). It checks if a span is an InvokeAgent span and removes `gen_ai.input.messages` from the serialized attributes. This only works for the A365 exporter because the `OTLPSpanExporter` never calls `_map_span`.

To make suppression work with any exporter, we move it into `_EnrichingBatchSpanProcessor.on_end()`, which runs before all exporters.

#### Step 1: Extend `EnrichedReadableSpan` to support attribute exclusion

`EnrichedReadableSpan` (`enriched_span.py`) currently only supports *adding* attributes. Add an `excluded_attribute_keys` parameter so attributes can also be *removed*:

```python
class EnrichedReadableSpan(ReadableSpan):
    def __init__(
        self,
        span: ReadableSpan,
        extra_attributes: dict,
        excluded_attribute_keys: set[str] | None = None,
    ):
        self._span = span
        self._extra_attributes = extra_attributes
        self._excluded_attribute_keys = excluded_attribute_keys or set()

    @property
    def attributes(self) -> types.Attributes:
        original = dict(self._span.attributes or {})
        original.update(self._extra_attributes)
        for key in self._excluded_attribute_keys:
            original.pop(key, None)
        return original
```

The new parameter is optional and defaults to empty — existing callers are unaffected.

#### Step 2: Pass `suppress_invoke_agent_input` to `_EnrichingBatchSpanProcessor`

```python
class _EnrichingBatchSpanProcessor(BatchSpanProcessor):
    def __init__(
        self,
        *args: object,
        suppress_invoke_agent_input: bool = False,
        **kwargs: object,
    ):
        super().__init__(*args, **kwargs)
        self._suppress_invoke_agent_input = suppress_invoke_agent_input

    def on_end(self, span: ReadableSpan) -> None:
        enriched_span = span

        # Apply registered enricher (framework extensions)
        enricher = get_span_enricher()
        if enricher is not None:
            try:
                enriched_span = enricher(span)
            except Exception:
                logger.exception(...)

        # Apply input message suppression for InvokeAgent spans
        if self._suppress_invoke_agent_input:
            attrs = enriched_span.attributes or {}
            operation_name = attrs.get(GEN_AI_OPERATION_NAME_KEY)
            if (
                enriched_span.name.startswith(INVOKE_AGENT_OPERATION_NAME)
                and operation_name == INVOKE_AGENT_OPERATION_NAME
            ):
                enriched_span = EnrichedReadableSpan(
                    enriched_span,
                    extra_attributes={},
                    excluded_attribute_keys={GEN_AI_INPUT_MESSAGES_KEY},
                )

        super().on_end(enriched_span)
```

#### Step 3: Wire it up in `config.py`

In `_configure_internal()`, pass `suppress_invoke_agent_input` to the batch processor:

```python
batch_processor = _EnrichingBatchSpanProcessor(
    exporter,
    suppress_invoke_agent_input=suppress_invoke_agent_input,
    **batch_processor_kwargs,
)
```

This works for both the A365 and Spectra exporter paths.

#### Step 4: Remove suppression from `_Agent365Exporter._map_span()`

Remove lines 274-284 from `agent365_exporter.py`. The suppression is now handled by the batch processor before the exporter sees the span. Also remove the `suppress_invoke_agent_input` parameter from `_Agent365Exporter.__init__()`.

### 5.4 Export surface changes

#### `exporters/__init__.py`

Add `SpectraExporterOptions` to exports:
```python
from .agent365_exporter_options import Agent365ExporterOptions
from .spectra_exporter_options import SpectraExporterOptions

__all__ = ["Agent365ExporterOptions", "SpectraExporterOptions"]
```

#### `core/__init__.py`

Add both options classes to the public API for import symmetry. Currently `Agent365ExporterOptions` is only exported from `exporters/__init__.py` — consumers must import from the deeper path. Adding it here alongside `SpectraExporterOptions` ensures consistent import ergonomics:

```python
from .exporters.agent365_exporter_options import Agent365ExporterOptions
from .exporters.spectra_exporter_options import SpectraExporterOptions
# ... in __all__:
"Agent365ExporterOptions",
"SpectraExporterOptions",
```

---

## 6. Compliance Checklist

| Check | Status |
|-------|--------|
| Copyright header on new files | Required |
| No `typing.Any` usage | Will follow — `SpectraExporterOptions` uses concrete types |
| No `_async` suffix on async methods | N/A — no async methods |
| Type hints on all parameters and return types | Yes |
| Explicit `None` checks (`is not None`) | Yes |
| Line length ≤ 100 characters | Yes |
| `Agent365ExporterOptions` API unchanged | Yes |
| Existing test suite passes without modification | Yes |
| No new package dependencies | Yes — `opentelemetry-exporter-otlp` already in core deps |

---

## 7. Test Strategy

### New test file: `tests/observability/core/test_spectra_exporter.py`

Tests follow the existing pattern in `test_agent365.py` (unittest.TestCase, Mock, patch):

**Core functionality:**

| Test | What it verifies |
|------|-----------------|
| `test_configure_with_spectra_options_default` | `configure()` succeeds with `SpectraExporterOptions()` (all defaults) via public API |
| `test_configure_with_spectra_options_creates_grpc_exporter` | gRPC `OTLPSpanExporter` created with correct endpoint and `insecure=True` |
| `test_configure_with_spectra_options_creates_http_exporter` | HTTP `OTLPSpanExporter` created when `protocol="http"` |
| `test_configure_with_spectra_options_custom_endpoint` | Custom endpoint is passed through to exporter |
| `test_configure_with_spectra_options_ignores_a365_env_var` | `ENABLE_A365_OBSERVABILITY_EXPORTER=true` does not create `_Agent365Exporter`; `is_agent365_exporter_enabled` is not called |
| `test_configure_with_spectra_options_batch_settings` | Batch processor kwargs extracted from `SpectraExporterOptions` |
| `test_configure_with_agent365_options_unchanged` | Existing A365 path still works identically (regression) |
| `test_spectra_exporter_options_defaults` | All default values are correct (`endpoint`, `protocol`, `insecure=True`, batch settings) |

**Edge cases and interactions:**

| Test | What it verifies |
|------|-----------------|
| `test_spectra_options_invalid_protocol_raises` | `SpectraExporterOptions(protocol="websocket")` raises `ValueError` |
| `test_configure_spectra_with_otlp_bolt_on` | With `SpectraExporterOptions` + `ENABLE_OTLP_EXPORTER=true`, two exporters are created (documented behavior) |
| `test_configure_spectra_with_suppress_invoke_agent_input` | `suppress_invoke_agent_input=True` with Spectra options creates batch processor with suppression enabled |
| `test_suppress_invoke_agent_input_strips_attribute_in_enriching_processor` | `_EnrichingBatchSpanProcessor` strips `gen_ai.input.messages` from InvokeAgent spans when flag is set |
| `test_enriched_span_excluded_attribute_keys` | `EnrichedReadableSpan` with `excluded_attribute_keys` removes specified attributes |

### Mocking strategy

- Mock `microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter` for gRPC tests (module-level import)
- Mock `microsoft_agents_a365.observability.core.config.OTLPSpanExporter` for HTTP tests (module-level import)
- Mock `_EnrichingBatchSpanProcessor` to verify batch kwargs
- Reset `_telemetry_manager` singleton in setUp/tearDown (existing pattern from `test_agent365.py:22-27`)

---

## 8. Consumer Usage

### Spectra deployment (Weave/Copilot Cowork) — zero config

```python
from microsoft_agents_a365.observability.core import configure, SpectraExporterOptions

configure(
    service_name="weave-agent",
    service_namespace="copilot-cowork",
    exporter_options=SpectraExporterOptions(),
)
```

### Spectra with custom settings

```python
configure(
    service_name="weave-agent",
    service_namespace="copilot-cowork",
    exporter_options=SpectraExporterOptions(
        endpoint="http://spectra-sidecar:4317",
        protocol="http",
        max_export_batch_size=1024,
    ),
)
```

### A365 deployment (unchanged)

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

## 9. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Spectra sidecar not running → traces silently dropped | Medium | Low (deployment issue) | OTLP exporter logs connection errors with retry. Document sidecar as deployment prereq. |
| Consumer accidentally passes both A365 env var + Spectra options | Low | Medium | Type-based dispatch means Spectra path is taken regardless. No ambiguity. |
| Consumer sets `insecure=False` for remote Spectra endpoint but forgets TLS setup | Low | Low | Only relevant for non-sidecar deployments. Default `insecure=True` is correct for localhost. |
| gRPC import fails if grpc extras not installed | Low | Low | `opentelemetry-exporter-otlp` (core dep) pulls in both gRPC and HTTP sub-packages |
| Union type confuses consumers | Low | Low | Clear docstrings. Only two concrete types. |

---

## 10. Interactions and Notes

### `ENABLE_OTLP_EXPORTER`

When `SpectraExporterOptions` is provided and `ENABLE_OTLP_EXPORTER=true` is also set, two OTLP exporters will be active simultaneously: the Spectra exporter and the generic OTLP bolt-on. This doubles memory queues and export I/O. This is documented and tested but is unlikely to be intentional in practice. Consumers should not set `ENABLE_OTLP_EXPORTER` when using `SpectraExporterOptions`.

---

## 11. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-14 | Initial design from brainstorm |
| 1.1 | 2026-03-14 | Review feedback: fixed `insecure` default to `True`, eliminated fallback duplication, added `protocol` validation, module-level gRPC import, export surface symmetry, added edge case tests |
| 1.2 | 2026-03-14 | Moved `suppress_invoke_agent_input` from `_Agent365Exporter._map_span()` to `_EnrichingBatchSpanProcessor.on_end()` so it works with both A365 and Spectra exporters. Extended `EnrichedReadableSpan` with `excluded_attribute_keys`. |

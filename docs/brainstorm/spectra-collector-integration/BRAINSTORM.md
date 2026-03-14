# Spectra Collector Integration — Brainstorm Working Document

**Status:** Complete
**Started:** 2026-03-14
**Last Updated:** 2026-03-14

---

## Problem Frame

**Trigger:** Weave/Copilot Cowork team needs to use Spectra Collector instead of A365 API directly. This is net-new — no consumer currently uses Spectra through this SDK.

**Scope:** Create a dedicated `SpectraExporterOptions` so consumers deploying with Spectra sidecars in K8s can configure the observability-core package to export traces to Spectra instead of A365.

**Key Context:**
- Spectra Collector is a sidecar OTEL Collector that accepts **standard OTLP** (gRPC on :4317, HTTP on :4318)
- Spectra is a **replacement** for A365 in certain deployments (not additive)
- No Spectra-specific attributes needed — tenant_id is already required by this library
- Spectra dependencies should remain optional

**Stakeholders:** Weave/Copilot Cowork team (first consumer)
**Constraints:** Optional dependencies, K8s sidecar deployment only

---

## Current State

### Exporter Pipeline Architecture

The `TelemetryManager.configure()` method (`config.py`) creates the exporter pipeline:

1. **Primary exporter** (lines 159-171): Either `_Agent365Exporter` (if `ENABLE_A365_OBSERVABILITY_EXPORTER=true` AND `token_resolver` provided) or `ConsoleSpanExporter` fallback
2. **Optional OTLP exporter** (lines 187-192): If `ENABLE_OTLP_EXPORTER=true`, adds an `OTLPSpanExporter` (auto-configured from OTEL env vars)
3. Both use `_EnrichingBatchSpanProcessor` which applies span enrichers before export

### Key Components

| Component | Role | Public? |
|-----------|------|---------|
| `configure()` | Entry point — takes `Agent365ExporterOptions` | Yes |
| `Agent365ExporterOptions` | Config for A365 exporter (token_resolver, cluster_category, batch settings) | Yes |
| `_Agent365Exporter` | Custom HTTP exporter — partitions by identity, POSTs to A365 API | No (internal) |
| `_EnrichingBatchSpanProcessor` | Batch processor with span enrichment hook | No (internal) |
| `OTLPSpanExporter` | Standard OTEL OTLP exporter (used for optional OTLP path) | From otel-sdk |

### What Works Well (Keep)
- `_EnrichingBatchSpanProcessor` — enrichment pipeline is exporter-agnostic
- `SpanProcessor` for agent span processing — independent of export destination
- All scope classes (`InvokeAgentScope`, `ExecuteToolScope`, etc.) — independent of exporter
- Extension instrumentors — they just register enrichers/processors, don't care about export

### What's Painful (Change Candidates)
- `configure()` is hardcoded to either A365 exporter or console fallback — no way to select Spectra
- `exporter_options` parameter is typed as `Agent365ExporterOptions` — not generic
- The OTLP exporter path (lines 187-192) is a bolt-on with no configuration surface

### What's Missing (Build)
- `SpectraExporterOptions` — configuration class for Spectra-specific settings
- Selection logic in `configure()` to choose Spectra exporter when configured
- Environment variable for enabling Spectra exporter

### Dependencies
- `opentelemetry-exporter-otlp` is already a **core dependency** (not optional) — used for the existing OTLP path
- Since Spectra accepts OTLP, no new dependencies needed for the exporter itself

---

## Requirements & Gaps

| # | Requirement | Layer | Status |
|---|-------------|-------|--------|
| R1 | Consumer can configure Spectra as the export destination instead of A365 | Configuration | **Gap** |
| R2 | Spectra exporter sends traces via OTLP to a sidecar endpoint (default `localhost:4317`) | Infrastructure | **Partial** |
| R3 | Span enrichment pipeline works identically regardless of exporter | Infrastructure | **Met** |
| R4 | Framework extensions work with Spectra without changes | Intelligence | **Met** |
| R5 | Spectra and A365 are mutually exclusive per deployment | Configuration | **Gap** |
| R6 | Spectra dependencies remain optional (no new deps needed) | Infrastructure | **Met** |
| R7 | Batch processor settings configurable for Spectra (client-side batching) | Configuration | **Gap** |

### What Changes vs What Stays

**MUST NOT change:** Scope classes, span enrichment pipeline, framework extensions, constants, `Agent365ExporterOptions` API

**MUST change:** `configure()` to accept Spectra options; exporter selection logic in `_configure_internal()`

**COULD change:** Extract shared batch settings into base class (deferred — only 2 exporters)

---

## Key Decisions

### Decision 1: Exporter configuration model
**Chosen: Separate `SpectraExporterOptions` class** alongside `Agent365ExporterOptions`. No shared base class — duplication of 4 batch fields is acceptable. Avoids changing existing class hierarchy.

### Decision 2: Exporter selection mechanism
**Chosen: Type-based dispatch.** Consumer passes `SpectraExporterOptions` or `Agent365ExporterOptions` to `configure()`. No env var magic — explicit in code.

### Decision 3: Relationship to `ENABLE_OTLP_EXPORTER`
**Chosen: Keep separate.** `ENABLE_OTLP_EXPORTER` remains a generic escape hatch. Spectra is a dedicated, opinionated integration. Different purposes, no conflict.

### Decision 4: Default endpoint and protocol
**Chosen: `SpectraExporterOptions` defaults to `http://localhost:4317` (gRPC).** Zero-config for K8s sidecar deployments. Consumer can override but shouldn't need to in the common case.

---

## Risks & Open Questions

### Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Sidecar not running → silent failure | Medium | OTLP exporter logs connection errors; document deployment prereqs |
| Consumer passes both A365 env var + Spectra options | Low | Spectra options take precedence; env var ignored |
| `insecure=False` default may fail on plain HTTP localhost | Low | Document: set `insecure=True` if sidecar doesn't have TLS |

### Open Questions (Resolved)
1. **Union type vs separate param** → Union type on `exporter_options`
2. **A365 env var behavior** → Ignored entirely when SpectraExporterOptions provided
3. **Insecure config** → Exposed, defaults to `False`
4. **Protocol config** → Exposed (`"grpc"` or `"http"`), defaults to `"grpc"`
5. **Package exports** → `SpectraExporterOptions` added to `__init__.py`
6. **Test strategy** → Mock `OTLPSpanExporter`

## Doc Map
- [TLDR.md](TLDR.md) — 1-page summary for stakeholders
- [ARCHITECTURE.md](ARCHITECTURE.md) — Full technical architecture proposal

---

## Session Log

### 2026-03-14 — Phase 1: Problem Framing
- Explored observability-core architecture: TelemetryManager singleton, A365 exporter, OTLP exporter, enriching batch processor
- Explored spectra-collector: OTLP-based sidecar, accepts standard OTEL traces/logs/metrics on localhost:4317/4318
- Key finding: existing `ENABLE_OTLP_EXPORTER` path already creates an `OTLPSpanExporter` — Spectra accepts OTLP natively
- User confirmed: Spectra replaces A365 in certain deployments (Weave/Copilot Cowork)
- User confirmed: No Spectra-specific attributes needed, dependencies should be optional

### 2026-03-14 — Phase 2: Current State Mapped
- Mapped exporter pipeline: configure() → A365Exporter or Console, plus optional OTLP
- Key gap: configure() is hardcoded to A365 exporter options — no way to select Spectra
- Key advantage: `opentelemetry-exporter-otlp` is already a core dep, enrichment pipeline is exporter-agnostic
- All scope classes, extensions, and instrumentors are independent of export destination

### 2026-03-14 — Phase 3: Requirements & Gaps
- 7 requirements identified; 3 met, 1 partial, 3 gaps
- Key gaps: configure() dispatch, exporter selection, batch settings for Spectra
- No changes needed to scopes, enrichment, extensions, or constants

### 2026-03-14 — Phase 4: Key Decisions
- Decision 1: Separate `SpectraExporterOptions` class (no shared base)
- Decision 2: Type-based dispatch in `configure()`
- Decision 3: Keep `ENABLE_OTLP_EXPORTER` separate from Spectra
- Decision 4: Default endpoint `http://localhost:4317` (gRPC) — zero-config for K8s sidecar
- User clarified: defaults are critical since Spectra is always a K8s sidecar

### 2026-03-14 — Phase 5: Risks & Open Questions
- All 6 open questions resolved by user
- Key decisions: union type on exporter_options, env var ignored for Spectra, insecure=False default, gRPC default, mock tests
- No blocking risks identified

### 2026-03-14 — Phase 6: Outputs
- Created TLDR.md and ARCHITECTURE.md
- Brainstorm complete

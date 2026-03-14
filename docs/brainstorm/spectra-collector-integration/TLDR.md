# Spectra Collector Integration — TLDR

**Date:** 2026-03-14
**Status:** Ready to build

## What

Add `SpectraExporterOptions` to the observability-core package so consumers deploying with Spectra Collector sidecars in K8s can export traces via OTLP instead of the A365 API.

## Why

Weave/Copilot Cowork needs Spectra Collector as their telemetry destination. Spectra replaces A365 in their deployment topology. The SDK currently only supports the A365 exporter or a raw OTLP bolt-on with no configuration surface.

## How

- New `SpectraExporterOptions` class with sensible defaults for K8s sidecar (`http://localhost:4317`, gRPC, insecure=false)
- `configure(exporter_options=...)` accepts `Agent365ExporterOptions | SpectraExporterOptions` — type-based dispatch selects the exporter
- When `SpectraExporterOptions` is provided, `ENABLE_A365_OBSERVABILITY_EXPORTER` env var is ignored
- Under the hood, creates an `OTLPSpanExporter` pointed at the Spectra endpoint — no new dependencies
- Enrichment pipeline, scope classes, and framework extensions work unchanged

## Key Decisions

1. **Separate options class** (not a shared base) — keeps things simple with only 2 exporters
2. **Type-based dispatch** — no env var magic, consumer explicitly chooses in code
3. **`ENABLE_OTLP_EXPORTER` stays separate** — generic escape hatch, different purpose
4. **Zero-config defaults** — endpoint `http://localhost:4317`, gRPC protocol, configurable but shouldn't need to change

## Scope

- **Changes:** `SpectraExporterOptions` (new file), `config.py` (exporter selection), `exporters/__init__.py` and `core/__init__.py` (exports), tests
- **No changes:** Scope classes, enrichment pipeline, framework extensions, constants, `Agent365ExporterOptions`

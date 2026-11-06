# Changelog — microsoft-agents-a365-runtime

All notable changes to this package will be documented in this file.

## [Unreleased]

### Breaking Changes

- Remove `get_observability_authentication_scope()` from
  `microsoft_agents_a365.runtime` and remove `PROD_OBSERVABILITY_SCOPE` and
  `PROD_OBSERVABILITY_CLUSTER_CATEGORY` from `runtime.environment_utils`.
  Observability has moved to `microsoft-opentelemetry`; follow the
  [migration guide](../../docs/observability-migration.md), including its
  route-specific authentication guidance. Generic Runtime utilities remain
  supported. The shared workspace release target is now `3.0.0`.

## [2.0.0] - 2026-10-20

### Breaking Changes

- **OBS authentication scope is app-only** —
  `get_observability_authentication_scope()` now returns the OBS resource
  `/.default` scope (`api://9b975845-388f-4429-889e-eab1ef63949c/.default`)
  instead of the delegated `Agent365.Observability.OtelWrite` scope. OBS export
  is S2S-only; use this scope with an app-only resolver for the exporting agent
  identity. Workload MCP/Graph/OBO authentication is unchanged.

# Changelog — microsoft-agents-a365-runtime

All notable changes to this package will be documented in this file.

## [Unreleased]

### Breaking Changes

- **OBS authentication scope is app-only** —
  `get_observability_authentication_scope()` now returns the OBS resource
  `/.default` scope (`api://9b975845-388f-4429-889e-eab1ef63949c/.default`)
  instead of the delegated `Agent365.Observability.OtelWrite` scope. OBS export
  is S2S-only; use this scope with an app-only resolver for the exporting agent
  identity. Workload MCP/Graph/OBO authentication is unchanged.

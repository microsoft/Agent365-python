# Changelog — microsoft-agents-a365-observability-hosting

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Breaking Changes

- **Hosting OBS token cache requires an app-only resolver** —
  `refresh_observability_token(agent_id, tenant_id, token_resolver)` acquires
  and caches app-only OBS tokens for export. The resolver receives the
  configured OBS scopes and must acquire a token for the exporting agent
  identity, not its blueprint or the workload's user. Acquisition failures
  propagate to the caller; empty tokens fail refresh and clear stale cache state.
- **`get_observability_token(...)` no longer exchanges tokens** — It returns the
  cached app-only token acquired by `refresh_observability_token`, or `None`.
- **Delegated OBS registration is a no-op** — `register_observability(...)`
  logs one error and stores no token. It never calls `Authorization.exchange_token`
  and never acquires a delegated OBS token.

### Changed

- The package now declares a direct dependency on
  `microsoft-agents-a365-runtime`.

### Fixed

- Channel scope helpers now fall back to `channel_data.productContext` for the
  sub-channel when the activity's `ChannelId` does not carry one.

### Migration

- Call and return `refresh_observability_token(agent_id, tenant_id, app_only_token_resolver)`
  from the exporter `token_resolver`.
- Keep workload MCP/Graph/OBO authentication unchanged; only OBS export
  authentication moves to app-only S2S.

## [1.0.0] - 2026-05-01

### Changed

- **`OutputLoggingMiddleware`** — Updated to use new scope APIs (`Request`, `SpanDetails`, `UserDetails`). Removed `TenantDetails` and `ExecutionType` dependencies. Middleware no longer gates on tenant presence.
- **`scope_helpers/utils.py`** — Removed `get_execution_type_pair()`.
- **`populate_baggage.py`** / **`populate_invoke_agent_scope.py`** — Removed execution type population.

# Changelog — microsoft-agents-a365-observability-hosting

All notable changes to this package will be documented in this file.

## [Unreleased]

### Changed

- **`OutputLoggingMiddleware`** — Updated to use new scope APIs (`Request`, `SpanDetails`, `UserDetails`). Removed `TenantDetails` and `ExecutionType` dependencies. Middleware no longer gates on tenant presence.
- **`scope_helpers/utils.py`** — Removed `get_execution_type_pair()`.
- **`populate_baggage.py`** / **`populate_invoke_agent_scope.py`** — Removed execution type population.

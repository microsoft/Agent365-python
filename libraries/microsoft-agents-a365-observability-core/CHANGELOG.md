# Changelog — microsoft-agents-a365-observability-core

All notable changes to this package will be documented in this file.

## [0.3.0]

### Breaking Changes

- **New permission required: `Agent365.Observability.OtelWrite`** — The observability exporter now requires this scope as both a delegated and application permission on your agent blueprint. See [Upgrade Instructions](#upgrade-instructions-observability-permission-for-existing-agents) below.

---

### Upgrade Instructions: Observability Permission for Existing Agents

Existing agent blueprints need `Agent365.Observability.OtelWrite` granted as both a **delegated permission** and an **application permission**. Choose either option below.

#### Option A — Agent 365 CLI (requires both config files)

Requires `a365.config.json` and `a365.generated.config.json` in your config directory, a Global Administrator account, and [Agent 365 CLI v1.1.139-preview](https://www.nuget.org/packages/Microsoft.Agents.A365.DevTools.Cli/1.1.139-preview) or later.

```
a365 setup admin --config-dir "<path-to-config-dir>"
```

This grants all missing permissions including the new Observability scopes.

#### Option B — Entra Portal (no config files required)

Requires Global Administrator access to the blueprint app registration.

1. Go to **Entra portal** > **App registrations** > select your Blueprint app
2. Go to **API permissions** > **Add a permission** > **APIs my organization uses** > search for `9b975845-388f-4429-889e-eab1ef63949c`
3. Select **Delegated permissions** > check `Agent365.Observability.OtelWrite` > **Add permissions**
4. Repeat step 2–3, this time select **Application permissions** > check `Agent365.Observability.OtelWrite` > **Add permissions**
5. Click **Grant admin consent** and confirm

Both `Agent365.Observability.OtelWrite` (Delegated) and `Agent365.Observability.OtelWrite` (Application) should show **Granted** status.

> **Note:** If your agent is autonomous, you only need the **Application permission**. The delegated permission is required for agents that authenticate via a user session.

---

## [0.2.1.dev46]

### Breaking Changes

- **`InvokeAgentDetails` renamed to `InvokeAgentScopeDetails`** — Now contains only scope-level config (`endpoint`). Agent identity (`AgentDetails`) is a separate parameter. `session_id` moved to `Request`.
- **`InvokeAgentScope.start()`**: New signature `start(request, invoke_scope_details, agent_details, caller_details?, span_details?)`. `request` is required.
- **`InferenceScope.start()`**: New signature `start(request, details, agent_details, user_details?, span_details?)`. `request` is required.
- **`ExecuteToolScope.start()`**: New signature `start(request, details, agent_details, user_details?, span_details?)`. Same pattern as `InferenceScope`.
- **`OutputScope.start()`**: New signature `start(request, response, agent_details, user_details?, span_details?)`. Same pattern.
- **`CallerDetails` renamed to `UserDetails`** — Fields renamed: `caller_id` → `user_id`, `caller_upn` → `user_email`, `caller_name` → `user_name`, `caller_client_ip` → `user_client_ip`.
- **`CallerDetails` is now a composite wrapper** — Groups `user_details: UserDetails` and `caller_agent_details: AgentDetails` for A2A scenarios.
- **`TenantDetails` removed** — `tenant_id` is now on `AgentDetails.tenant_id`. Removed from all scope `start()` methods.
- **`ExecutionType` enum removed** — Removed from `Request`. `GEN_AI_EXECUTION_TYPE_KEY` constant also removed.
- **`AgentDetails` fields renamed** — `agent_auid` → `agentic_user_id`, `agent_upn` → `agentic_user_email`. `conversation_id` moved to `Request`.
- **`Request` model updated** — Removed `execution_type`. Added `conversation_id`. `content` is now optional.
- **`BaggageBuilder` methods renamed** — `agent_upn()` → `agentic_user_email()`, `agent_auid()` → `agentic_user_id()`, `caller_id()` → `user_id()`, `caller_name()` → `user_name()`, `caller_upn()` → `user_email()`, `caller_client_ip()` → `user_client_ip()`.

### Added

- **`SpanDetails`** — Groups `span_kind`, `parent_context`, `start_time`, `end_time` for scope construction.
- **`UserDetails`** — Human caller identity with `user_id`, `user_email`, `user_name`, `user_client_ip`.
- **`CallerDetails`** (new wrapper) — Groups `user_details` and `caller_agent_details` for A2A scenarios.
- **`InvokeAgentScopeDetails`** — Scope-level config with `endpoint` only.
- **`Request.conversation_id`** — Conversation ID field on the unified `Request` model.
- **`ERROR_TYPE_CANCELLED`** constant — `"TaskCanceledException"`, used by `record_cancellation()`.
- **`OutputScope`** now exported from `microsoft_agents_a365.observability.core`.

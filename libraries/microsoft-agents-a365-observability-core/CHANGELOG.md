# Changelog — microsoft-agents-a365-observability-core

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Breaking Changes

- **OBS exports always use `/observabilityService`** — The `use_s2s_endpoint`
  option is deprecated and ignored, even when `False`. Exports no longer select
  or fall back to `/observability`. Provide an app-only OBS token independently
  of your agent's workload auth; the S2S service rejects delegated `scp` tokens.
- **OBS export requires the configured app-only resolver** — The exporter uses
  only `token_resolver(agent_id, tenant_id)` for Agent 365 authentication. If
  the Agent 365 exporter is enabled without a resolver, the existing console
  fallback is kept and nothing is sent to Agent 365. Empty tokens or acquisition
  failures fail export without an HTTP request or delegated fallback. The
  exporter invokes the resolver on every export batch/identity group, so
  resolvers must cache the acquired token and refresh only near expiry.
- **Manual inference operation names and span-name prefixes now use canonical
  OpenTelemetry values** — `Chat`, `TextCompletion`, and `GenerateContent`
  become `chat`, `text_completion`, and `generate_content`, respectively.
  For example, `Chat gpt-4` becomes `chat gpt-4`. The Agent 365 exporter
  recognizes the canonical names (the legacy `Chat` value is still accepted),
  so text-completion and generate-content spans that were previously filtered
  out are now exported to Agent 365.
- **`InferenceCallDetails` now validates model identity during construction** —
  `model` and `responseModel` are stripped and whitespace-only values are
  treated as `None`. If both are missing, empty, or whitespace-only,
  construction raises `ValueError`. Previously these values were accepted
  without validation. This happens before an `InferenceScope` is created.
- **Message payloads serialize as a plain JSON array** — `gen_ai.input.messages`
  and `gen_ai.output.messages` are now serialized per the OpenTelemetry GenAI
  semantic conventions as `[{"role": ..., "parts": [...]}]` instead of the
  `{"version": "0.1.0", "messages": [...]}` wrapper. The
  `A365_MESSAGE_SCHEMA_VERSION` constant and the `version` field on
  `InputMessages`/`OutputMessages` are removed, and `OutputMessage.finish_reason`
  now defaults to `"stop"` instead of `None`.

### Added

- **`ApplyGuardrailScope`** for tracing security guardrail evaluations
  (`apply_guardrail` operation), with supporting `GuardrailDetails`,
  `GuardrailFinding`, `GuardrailDecisionType`, `GuardrailRiskSeverity`, and
  `GuardrailTargetType` types and `microsoft.guardian.*` /
  `microsoft.security.*` attribute constants. `apply_guardrail` spans are
  exported to Agent 365.
- **`AgentDetails.agent_type`** and **`BaggageBuilder.agent_type()`** emit
  `gen_ai.agent.type`. Both accept an `AgentType` enum member or a string;
  enum members are emitted as their string `.value`. The new dataclass field is
  appended after existing fields, preserving positional-argument compatibility.
- **`InferenceCallDetails.responseModel`**, **`cacheReadInputTokens`**, and
  **`cacheWriteInputTokens`** emit `gen_ai.response.model`,
  `gen_ai.usage.cache_read.input_tokens`, and
  `gen_ai.usage.cache_write.input_tokens`. `model` is now optional when
  `responseModel` is supplied. The new fields are appended after existing
  fields, preserving positional-argument compatibility.
- **`InferenceScope.record_cache_read_input_tokens()`** and
  **`record_cache_write_input_tokens()`**.
- **`InferenceOperationType.canonical_name`** returns the canonical lowercase
  OpenTelemetry operation name.

### Changed

- `InferenceScope` emits `server.port` as an integer instead of a string.

### Fixed

- Scopes and the Agent 365 exporter no longer raise `AttributeError` when the
  tracer returns a `NonRecordingSpan` (for example, when the token resolver
  returns `None` on the first turn); span context is read via
  `get_span_context()`.

### Migration

- Request the OBS resource `/.default` scope
  (`api://9b975845-388f-4429-889e-eab1ef63949c/.default`) for the exporting
  agent identity. Do not use delegated `Agent365.Observability.OtelWrite` tokens
  for OBS export.
- Validate resolver tokens before returning them: reject any `scp` claim and any
  `idtyp` other than `app`; when `idtyp` is absent, accept only a non-empty
  `roles` array or a non-empty `oid` equal to `sub`; verify `aud` is the OBS
  resource and the token is not expired.
- Update case-sensitive operation-name and span-name filters, dashboards, and
  alerts to the canonical values above, or compare case-insensitively.
- Supply a non-blank `model` or `responseModel` when constructing
  `InferenceCallDetails`; validate optional configuration before constructing
  the telemetry object so missing model identity does not interrupt a request.
- Update consumers that parse `gen_ai.input.messages` /
  `gen_ai.output.messages` to expect a JSON array rather than a
  `{version, messages}` object, and remove references to
  `A365_MESSAGE_SCHEMA_VERSION`.

## [1.0.0] - 2026-05-01

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

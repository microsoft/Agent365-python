# microsoft-agents-a365-tooling-extensions-agenthooks

[![PyPI](https://img.shields.io/pypi/v/microsoft-agents-a365-tooling-extensions-agenthooks?label=PyPI&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-tooling-extensions-agenthooks)
[![PyPI Downloads](https://img.shields.io/pypi/dm/microsoft-agents-a365-tooling-extensions-agenthooks?label=Downloads&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-tooling-extensions-agenthooks)

Microsoft Agent 365 real-time protection on the [agent-hooks](https://github.com/responsibleai/agent-hooks)
control contract (AGENT-HOOKS-0.1), using the Python package
[`agent-hooks-sdk`](https://pypi.org/project/agent-hooks-sdk/) (imported as `agent_hooks`): Microsoft
Defender for AI (`A365DefenderInterceptor`) and Microsoft Purview data loss prevention
(`A365PurviewInterceptor`, see [Microsoft Purview data loss prevention](#microsoft-purview-data-loss-prevention-dlp)).
Both can be registered on one emitter.

`A365DefenderInterceptor` is an agent-hooks interceptor for Microsoft Defender for AI. For each context
the host emits at the four points Defender evaluates, the prevention endpoint
(`POST .../v1/protection/evaluate`) receives a fitted copy of the context: normalized to Defender's
request validation and fitted to a size budget (see [Long content](#verdicts)), keeping the context's
session, sequence and tool call ids. The host's context is not modified. Defender's verdict decides:

| agent-hooks point | When | On `deny` |
|---|---|---|
| `input` | the user's message, before the agent runs | the agent does not run |
| `pre_tool_call` | a tool call, before it runs | the tool does not run |
| `post_tool_call` | a tool result, before the agent uses it | the result is withheld |
| `output` | the reply, before it is sent | the reply is replaced |

Other points (`agent_startup`, model calls, `agent_shutdown`) are allowed without a call.

The Defender client itself (`DefenderRtpClient`, in `microsoft_agents_a365.tooling.protection.defender`)
is part of `microsoft-agents-a365-tooling` and does not depend on agent-hooks.

## Installation

```bash
pip install microsoft-agents-a365-tooling-extensions-agenthooks
```

`agent-hooks-sdk` is a prerelease package with a native core. It ships wheels for Windows x64, Linux
x86_64 and aarch64 (manylinux), and macOS; there are no musl (Alpine) wheels.

## Authentication

Calls carry the **agent identity's own app-only token** in the agent's tenant, for the Defender API
(`api://86a21212-634e-4553-b3d6-e477e4c9d9ec`, application permission `RealtimeProtection.Evaluate.All`).
This is the same authority as Observability S2S export: `DefenderRtpTokenResolvers.from_agentic_connection`
asks the agent's connection for the agent identity's assertion (`get_agentic_application_token`) and
exchanges it at Entra for the Defender token. The client caches the token per agent, tenant and scope
until it expires. Within five minutes of expiry, a call refreshes it in the background and keeps using
the cached token, also when the refresh fails. `prefetch_access_token` acquires the token ahead of the
first evaluation. The endpoint and the token authority must be HTTPS URLs, and redirects are not
followed, so the token and the assertion never travel in plaintext or to another host.

### Granting the Defender permission

Defender accepts only callers whose app-only token carries the application permission
`RealtimeProtection.Evaluate.All` on the Defender API (`86a21212-634e-4553-b3d6-e477e4c9d9ec`).
[microsoft/Agent365-devTools#485](https://github.com/microsoft/Agent365-devTools/pull/485) adds this to
`a365 setup`. Until it ships, a tenant administrator grants it once per agent blueprint, and every agent
identity created from the blueprint inherits it:

1. If the tenant has no service principal for the Defender API yet, create one:
   `az ad sp create --id 86a21212-634e-4553-b3d6-e477e4c9d9ec`.
2. Assign the app role to the blueprint's service principal:
   `POST https://graph.microsoft.com/v1.0/servicePrincipals/{blueprint-sp-object-id}/appRoleAssignments`
   with `principalId` (the blueprint SP), `resourceId` (the Defender API SP) and `appRoleId` (the id of
   `RealtimeProtection.Evaluate.All` in that SP's `appRoles`). Requires Global Administrator or Privileged
   Role Administrator.
3. Make it inheritable:
   `POST https://graph.microsoft.com/beta/applications/microsoft.graph.agentIdentityBlueprint/{blueprint-object-id}/inheritablePermissions`
   with
   `{"resourceAppId":"86a21212-634e-4553-b3d6-e477e4c9d9ec","inheritableScopes":{"@odata.type":"#microsoft.graph.allAllowedScopes","kind":"allAllowed"},"inheritableRoles":{"@odata.type":"#microsoft.graph.allAllowedRoles","kind":"allAllowed"}}`.
   Requires Agent ID Administrator or Global Administrator.

The tenant must also be onboarded to Defender for AI; otherwise Defender returns 403, which follows the
fail mode.

## Usage

```python
from agent_hooks import AgentContextBuilder
from microsoft_agents_a365.tooling.extensions.agenthooks import (
    A365DefenderCall,
    A365DefenderInterceptor,
    add_a365_defender,
    create_protection_emitter,
)
from microsoft_agents_a365.tooling.protection.defender import (
    DefenderRtpAgentContext,
    DefenderRtpClient,
    DefenderRtpOptions,
    DefenderRtpTokenResolvers,
)

defender = DefenderRtpClient(DefenderRtpOptions.from_environment())
tokens = DefenderRtpTokenResolvers.from_agentic_connection(
    connection_manager.get_default_connection()
)

activity = turn_context.activity
agent = DefenderRtpAgentContext(
    agent_id=activity.get_agentic_instance_id(),  # the agent identity
    tenant_id=activity.get_agentic_tenant_id(),  # the agent's tenant
    request_id=activity.id,
    user_id=activity.from_property.aad_object_id,
)

emitter = add_a365_defender(
    create_protection_emitter(defender=defender.options),
    A365DefenderInterceptor(
        defender,
        lambda context: A365DefenderCall(agent, tokens),
        lambda result: logger.info(
            "Defender %s allowed=%s evaluated=%s cid=%s",
            result.interception_point,
            result.allowed,
            result.evaluated,
            result.correlation_id,
        ),
    ),
)

builder = AgentContextBuilder(
    agent_id=agent.agent_id,
    framework="agent-framework",
    session_id=activity.conversation.id,
    agent_name="SampleAgent",
)
record = await emitter.emit_unchecked(builder.input(content=user_message))
if not record.proceeds:
    ...  # blocked: record.verdict.message
```

The call resolver may also be async. It runs only for the four points Defender evaluates while
Defender RTP is enabled. Returning `None` (for example for a turn that has no agent identity) follows the
fail mode, like an unavailable Defender: no call is made, and `on_evaluated` receives the not-evaluated
result. An exception from the call resolver, or from the token resolver, also follows the fail mode
instead of failing the emission. Only the exception's type reaches the verdict and the interception record
(`evaluation failed (<type>)`), since its message can carry credentials or content; the exception itself is
logged. `on_evaluated` runs on a worker thread once the verdict is decided, outside the emitter's
interceptor timeout, so a slow or failing callback can't change the verdict. `emitter.emit(...)` raises
`agent_hooks.InterceptionBlocked` instead of returning a record that does not proceed.

`create_protection_emitter` returns an enforce-mode emitter with the `parallel/strictest` profile (an
action proceeds only when every interceptor allows it) and a per-interceptor timeout of the Defender
timeout plus two seconds. Token acquisition and the Defender call share one deadline, the Defender timeout,
so the client applies its fail mode before the emitter's timeout fires.

Use `create_protection_emitter`, or give your own emitter an interceptor timeout above the Defender
timeout. agent-hooks' default interceptor timeout (`InterceptionEmitter(timeout=5.0)`) is below the
client's default of 10 seconds, and an emitter timeout is a deny (`host_error:interceptor_timeout`)
whatever the fail mode, so a slow Defender call would block even when failing open:

```python
emitter = InterceptionEmitter(timeout=defender.options.timeout_seconds + 2)
add_a365_defender(emitter, interceptor)
```

## Verdicts

| Defender result | agent-hooks verdict |
|---|---|
| `allow` (with any warnings and labels) | `allow`, keeping Defender's warnings and `result_labels`; a warning reason that is empty or in the `host_error:` namespace agent-hooks reserves becomes `defender:warning` |
| `deny` | `deny`, reason `defender:block:<Defender reason>`, Defender's message, labels, and evidence `urn:a365:defender:<correlation id>` |
| `transform` | `deny`: this SDK version does not apply Defender's rewrite |
| `allow` of a truncated copy (content over the limit, or the called tool's declaration cut or not found among the first 10,000) | not authoritative: follows the fail mode, like no verdict |
| no verdict, fail open (default) | `allow` with a `defender:unverified` warning carrying the error |
| no verdict, fail closed | `deny`, reason `runtime_error:defender_unverified`, never reported as a detection |

**Long content.** Each content string sent is cut to `A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS` (default
20000), and all content in one request shares a budget of four times that, so the request and the time to
prepare it stay bounded. The content under decision (the user's message, a tool call's arguments, a tool
result, or the reply) is sent twice, as the point's field and as `target`, so it may use half of the
budget. The rest goes, in order, to the called tool's declaration (below), the call's arguments at
`post_tool_call` (already evaluated at `pre_tool_call`), the other tool declarations, the most recent
messages, extensions, and any other member. The envelope (agent, session, tenant, actor, ids, names and
roles) is built from its spec fields alone and never cut. When the content under decision doesn't fit, Defender
evaluates a truncated copy, so its verdict can't cover the rest. A Defender `deny` (or `transform`) still
blocks, but an `allow` follows the fail mode (`DefenderRtpEvaluationResult.truncated` is true): fail open
allows with a `defender:unverified` warning, and fail closed blocks. Raise
`A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS` for agents that handle long content; evaluating long content in
chunks is a follow-up.

**The called tool's declaration.** At `pre_tool_call` and `post_tool_call`, Defender's verdict also depends
on how the called tool is declared. Its declaration is searched for by name among the first 10,000 entries
of `tools` and charged to the budget right after the content under decision, ahead of the call's arguments
at `post_tool_call` and of the other declarations, which follow in your order as the budget allows. If its
description or schema had to be cut, or `tools` is longer than 10,000 entries and the called tool isn't
among the first 10,000, an `allow` follows the fail mode in the same way. A list of at most 10,000 entries
that doesn't declare the called tool is fine.

Strings are always sent as valid Unicode (a lone surrogate becomes U+FFFD, so it can't keep the request
from being sent), NaN and infinities are sent as text, and nesting deeper than 32 levels is cut like long
content. Message histories, extension namespaces and the tool declarations after the called tool's are read
only as far as the budget reaches, so a long one doesn't slow the call down. A context member, verdict
member or error body of an unexpected shape is ignored rather than failing the evaluation.

## Configuration

| Variable | Meaning |
|---|---|
| `ENABLE_A365_DEFENDER_RTP` | `true` (also `1`, `yes`, `on`) to call Defender; `false` (`0`, `no`, `off`) or unset not to; any other value is rejected |
| `A365_DEFENDER_RTP_ENDPOINT` | the prevention endpoint, `https://<host>/v1/protection/evaluate` (HTTPS only) |
| `A365_DEFENDER_RTP_FAIL_MODE` | `open` (default) or `closed`, which blocks when no verdict is obtained; any other value is rejected |
| `A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS` | one deadline for token acquisition and the call (default 10000) |
| `A365_DEFENDER_RTP_AUTHENTICATION_SCOPE` | overrides the Defender API scope |
| `A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS` | cuts each content string (default 20000); all content in a request shares four times that. Content under decision beyond it follows the fail mode unless Defender denies |

Every call sends a unique `x-ms-correlation-id`, returned as `DefenderRtpEvaluationResult.correlation_id`;
Defender logs each evaluation under it. A `400` reports the failed validation rule in `error`. A timeout,
transport or token failure, non-2xx response, or response without a verdict is not evaluated and follows
the fail mode.

## Microsoft Purview data loss prevention (DLP)

`A365PurviewInterceptor` (registered as `purview`) sends the user's message and the agent's reply to
Microsoft Purview through the Microsoft Graph
[`processContent`](https://learn.microsoft.com/graph/api/userdatasecurityandgovernance-processcontent) API.
Purview applies the tenant's DLP policies scoped to the agent's application, records the Purview audit event
(shown in Purview Audit and in Data Security Posture Management for AI), and returns the policy actions. The
client (`PurviewDlpClient`, in `microsoft_agents_a365.tooling.protection.purview`) is part of
`microsoft-agents-a365-tooling` and does not depend on agent-hooks.

| agent-hooks point | Purview activity | Behavior |
|---|---|---|
| `input` | `uploadText`: the user's message | awaited; a policy that blocks it denies, and the agent does not run |
| `output` | `downloadText`: the reply | `audit` (default): sent in the background, and the reply is allowed at once; `enforce`: awaited and mapped like `input` |

Other points (tool calls and results, model calls, `agent_startup`, `agent_shutdown`) are allowed without a
call, as is content without text. Structured content (for example a list of content parts) is sent as its
string and number values in order, one per line. Purview DLP policies for custom AI apps restrict uploaded
text, not downloaded text, which is why replies are audited by default.

### Purview authentication

`processContent` is called as a user: `POST {graph}/me/dataSecurityAndGovernance/processContent` with a
delegated token carrying `Content.Process.User`, or `.../users/{id}/...` with an application token carrying
the `Content.Process.User` or `Content.Process.All` application permission. A `PurviewDlpTokenResolver`
returns a `PurviewDlpToken(access_token, user_id=None)`: `user_id` `None` calls `/me`, and a user id calls
`/users/{user_id}`.

- `PurviewDlpTokenResolvers.from_agentic_user(connection)` (validated end to end): the agent's **agentic
  user**'s delegated Microsoft Graph token, issued through the agent's connection
  (`get_agentic_user_token`, which `MsalAuth` implements: the blueprint credential issues the agent identity's
  assertion, which is exchanged for the agentic user's token); it evaluates as `/me`. Set
  `PurviewDlpAgentContext.agentic_user_id` from the incoming activity (`activity.get_agentic_user()`).
  `microsoft-agents-hosting-core` 0.8 and later pass the agent's tenant to `get_agentic_user_token`; 0.7 and
  earlier don't, and the resolver supports both. Tokens are cached per tenant, agent, agentic user and scope
  until shortly before they expire, so create the resolver once: concurrent evaluations share one
  acquisition, a failure is never cached, and within five minutes of expiry a call refreshes the token in the
  background and keeps using the cached one, also when the refresh fails.
- `PurviewDlpTokenResolvers.from_access_token_provider(get_token, user_id=None)`: a Graph token your host
  supplies, for example an on-behalf-of token for the signed-in user (`/me`), or an application token with
  the user to evaluate as (`/users/{user_id}`). The application path hasn't been validated end to end yet.
  The SDK never caches these tokens, since they may be for a user the agent context doesn't identify: the
  provider is called for every evaluation, so it should cache its tokens itself (MSAL does).

A synchronous token resolver or provider runs on a worker thread. Token acquisition and the call share one
deadline, the Purview timeout. The Graph base URL must be an HTTPS URL, and redirects are not followed, so
the token and the content never travel in plaintext or to another host.

The SDK doesn't call `protectionScopes/compute`: it sends every message (and reply) and lets
`processContent` decide, so it needs no `ProtectionScopes.Compute.User` permission and caches no protection
scope state.

### Tenant prerequisites

1. **Licensing and billing.** Microsoft Purview licensing for the users and agents (for example Microsoft 365
   E5 or E5 Compliance), pay-as-you-go billing for Purview's AI features, and Data Security Posture
   Management (DSPM) for AI onboarded. Without them, `processContent` returns no policy actions, so nothing is
   blocked and no error is reported.
2. **A DLP policy for the agent.** In the Purview portal, create a DLP policy whose only location is the
   AI-app location (**Managed cloud apps**, the `Applications` workload) scoped to the agent blueprint's
   application id, which is the `applicationLocation` the SDK sends (`PurviewDlpAgentContext.application_id`
   overrides it). Add a rule that matches the sensitive information types to protect (for example credit card
   numbers) and restricts `UploadText` with **Block**, and turn the policy on. A policy can take up to an hour
   to apply.
3. **The delegated permission.** Add `Content.Process.User` to the agent blueprint's tenant-wide
   (`AllPrincipals`) delegated Microsoft Graph permission grant. Append it to the grant's existing scopes
   (`PATCH https://graph.microsoft.com/v1.0/oauth2PermissionGrants/{grant-id}` with the current `scope` plus
   `Content.Process.User`); never replace them, since the agent relies on the others. The blueprint's
   inheritable Microsoft Graph permissions (kind `allAllowed`, which `a365 setup` configures) pass the scope to
   every agent identity's agentic user.

### Purview usage

```python
from microsoft_agents_a365.tooling.extensions.agenthooks import (
    A365PurviewCall,
    A365PurviewInterceptor,
    add_a365_defender,
    add_a365_purview,
    create_protection_emitter,
)
from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpAgentContext,
    PurviewDlpClient,
    PurviewDlpOptions,
    PurviewDlpTokenResolvers,
)

connection = connection_manager.get_default_connection()
purview = PurviewDlpClient(PurviewDlpOptions.from_environment())
graph_tokens = PurviewDlpTokenResolvers.from_agentic_user(connection)

activity = turn_context.activity
purview_agent = PurviewDlpAgentContext(
    agent_id=activity.get_agentic_instance_id(),  # the agent identity
    tenant_id=activity.get_agentic_tenant_id(),  # the agent's tenant
    agentic_user_id=activity.get_agentic_user(),  # evaluates as the agentic user (/me)
    blueprint_id=connection.configuration.CLIENT_ID,  # the agent blueprint, which DLP policies are scoped to
    agent_name="SampleAgent",
)

# Defender and Purview on one emitter: an action proceeds only when both allow it.
emitter = create_protection_emitter(defender=defender.options, purview=purview.options)
add_a365_defender(emitter, defender_interceptor)  # see Usage above
add_a365_purview(
    emitter,
    A365PurviewInterceptor(
        purview,
        lambda context: A365PurviewCall(purview_agent, graph_tokens),
        lambda result: logger.info(
            "Purview %s allowed=%s evaluated=%s client-request-id=%s",
            result.activity,
            result.allowed,
            result.evaluated,
            result.correlation_id,
        ),
    ),
)

record = await emitter.emit_unchecked(builder.input(content=user_message))
if not record.proceeds:
    ...  # blocked: record.verdict.reason is "purview:block" or a Defender reason
```

The call resolver may be async. It runs only for content with text at `input` and `output` while Purview DLP
is enabled. Returning `None` (for example for a turn without an agentic user), or an exception from the call
or token resolver, follows the fail mode, as for Defender; only an exception's type reaches the verdict. When
the `PurviewDlpAgentContext` has no `agent_name`, the context's `agent.name` names the agent (and without
either, its agent identity id does, since Purview requires a name). `on_evaluated` receives every evaluation,
reply audits included, on a worker thread once the verdict is decided.

`create_protection_emitter(defender=..., purview=...)` sets the interceptor timeout to the Defender timeout
(the Defender default when no Defender options are given) or, when the Purview options are enabled, to the
slower of the Defender and Purview timeouts, plus two seconds; so each client's own deadline and fail mode
apply first, and a Defender-only emitter keeps its timeout. Its `parallel/strictest` profile gives every
interceptor the same context and lets a deny from either one block. agent-hooks 0.1 runs the interceptors of a
parallel profile one after the other, so at `input` the latency is Defender's plus Purview's. With an emitter
of your own, set its timeout above the Purview timeout too.

### Purview decisions

| Purview result | agent-hooks verdict |
|---|---|
| a policy action whose `restrictionAction` is `block` or whose `action` is `blockAccess` (any case), also beside processing errors or malformed actions, and for truncated content | `deny`, reason `purview:block`, evidence `urn:a365:purview:<client-request-id>`, and the message "The request was blocked by a Microsoft Purview data loss prevention policy." (at `input`) or "The response was blocked by a Microsoft Purview data loss prevention policy." (at `output`) |
| a list of policy actions without a block, or `202`/`204` | `allow`; the actions are counted in `decision.action_count` |
| an allow of truncated content | not authoritative: follows the fail mode, like no verdict |
| no verdict, fail open (default) | `allow` with a `purview:unverified` warning carrying the error |
| no verdict, fail closed | `deny`, reason `runtime_error:purview_unverified`, never reported as a detection |

No verdict means a timeout, transport or token failure, a non-2xx response, a body that is not a JSON object
or has no list of policy actions, a policy action of another shape, `processingErrors` (Graph reports a request
it rejected inline, in an HTTP 200), no agent identity, or an error from the call or token resolver. `error`
carries at most an exception's type, never a response body or a token, and `block_reason` the user-facing
message.

**Reply audits.** In the `audit` response mode the reply is never held or blocked: its evaluation runs in a
task of its own, bounded by the Purview timeout and untouched by the emitter's timeout or cancellation, and
its result (evaluated or not) goes to `on_evaluated`. The fail mode applies to awaited evaluations only.
`await interceptor.wait_for_pending_audits()` waits for the audits in flight, for example before shutdown.

**Long content.** Content longer than `A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS` (default 100000) is cut and
sent with `isTruncated: true`. A block still blocks, but an allow doesn't cover what was cut, so it follows the
fail mode (`PurviewDlpEvaluationResult.truncated` is true). Structured content is read only until its text is
past the limit; when the text read so far is blank but the content goes on, Purview is not called and the fail
mode applies, since the rest was never read. Strings are always sent as valid Unicode.

**The request.** Each call sends one new id as the `client-request-id` header and as the content entry's
`identifier`, returned as `correlation_id` (Graph logs the request under it); the conversation (`session.id`)
as the entry's `correlationId` and the context's `sequence` as its `sequenceNumber`; the agent (the agent
identity as `identifier`, its name, its version, `1.0` by default, and `blueprintId`, left out when unknown);
`contentCategory` `ai`; and the application location (the blueprint id, then the agent identity id).
Microsoft Graph v1.0 accepts the agent and `contentCategory`. The entry's `name` (`<agent name> <activity>`)
is never empty: Graph rejects an entry without one as a processing error in an HTTP 200.

### Purview configuration

| Variable | Meaning |
|---|---|
| `ENABLE_A365_PURVIEW_DLP` | `true` (also `1`, `yes`, `on`) to call Purview; `false` (`0`, `no`, `off`) or unset not to; any other value is rejected |
| `A365_PURVIEW_DLP_GRAPH_BASE_URL` | the Microsoft Graph base URL (default `https://graph.microsoft.com/v1.0`; HTTPS only) |
| `A365_PURVIEW_DLP_AUTHENTICATION_SCOPE` | the token scope (default `https://graph.microsoft.com/.default`) |
| `A365_PURVIEW_DLP_FAIL_MODE` | `open` (default) or `closed`, which blocks when no decision is obtained; any other value is rejected |
| `A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS` | one deadline for token acquisition and the call (default 10000) |
| `A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS` | content sent per evaluation (default 100000); content beyond it follows the fail mode unless Purview blocks |
| `A365_PURVIEW_DLP_RESPONSE_MODE` | `audit` (default) or `enforce` for the reply; any other value is rejected |

### Purview limitations

- Tool calls and tool results aren't sent to Purview; Defender evaluates them.
- Replies are audited by default, since Purview DLP policies for custom AI apps can't block `downloadText`.
- The application path (an application token for `/users/{id}`) hasn't been validated end to end.
- `protectionScopes/compute` (and caching its result) isn't used.

## Support

For issues, questions, or feedback:

- File issues in the [GitHub Issues](https://github.com/microsoft/Agent365-python/issues) section
- See the [main documentation](../../README.md) for more information

## Trademarks

*Microsoft, Windows, Microsoft Azure and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.*

## License

Copyright (c) Microsoft Corporation. All rights reserved.

Licensed under the MIT License - see the [LICENSE](../../LICENSE.md) file for details.

# microsoft-agents-a365-tooling-extensions-agenthooks

[![PyPI](https://img.shields.io/pypi/v/microsoft-agents-a365-tooling-extensions-agenthooks?label=PyPI&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-tooling-extensions-agenthooks)
[![PyPI Downloads](https://img.shields.io/pypi/dm/microsoft-agents-a365-tooling-extensions-agenthooks?label=Downloads&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-tooling-extensions-agenthooks)

Microsoft Agent 365 real-time protection on the [agent-hooks](https://github.com/responsibleai/agent-hooks)
control contract (AGENT-HOOKS-0.1), using the Python package
[`agent-hooks-sdk`](https://pypi.org/project/agent-hooks-sdk/) (imported as `agent_hooks`).

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

## Support

For issues, questions, or feedback:

- File issues in the [GitHub Issues](https://github.com/microsoft/Agent365-python/issues) section
- See the [main documentation](../../README.md) for more information

## Trademarks

*Microsoft, Windows, Microsoft Azure and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.*

## License

Copyright (c) Microsoft Corporation. All rights reserved.

Licensed under the MIT License - see the [LICENSE](../../LICENSE.md) file for details.

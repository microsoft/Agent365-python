# Tooling Extensions - agent-hooks - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-agenthooks` package.

## Overview

This extension plugs Microsoft Defender for AI real-time protection (Defender RTP) and Microsoft Purview data loss
prevention (DLP) into hosts that implement the [agent-hooks](https://github.com/responsibleai/agent-hooks) control
contract (AGENT-HOOKS-0.1). The host emits an agent-hooks context at each interception point;
`A365DefenderInterceptor` posts it to Defender's prevention endpoint through `DefenderRtpClient`, and
`A365PurviewInterceptor` sends the user's message and the agent's reply to Purview through `PurviewDlpClient` (both
clients from `microsoft-agents-a365-tooling`), and each returns its verdict to the emitter.

The clients live in the core tooling package and have no agent-hooks dependency. agent-hooks ships a native
core for only some platforms (no musl), so only agents that opt in to this extension take it on. Defender receives a
fitted copy of each context (normalized to its request validation and fitted to a size budget); the host's context is
not modified.

## Key Components

### A365DefenderInterceptor

An agent-hooks interceptor (`intercept(context) -> Verdict`, async), registered under the name `defender`.

```python
from microsoft_agents_a365.tooling.extensions.agenthooks import (
    A365DefenderCall,
    A365DefenderInterceptor,
    add_a365_defender,
    create_protection_emitter,
)

emitter = add_a365_defender(
    create_protection_emitter(defender=client.options),
    A365DefenderInterceptor(client, lambda context: A365DefenderCall(agent, tokens), on_evaluated),
)
record = await emitter.emit_unchecked(builder.input(content=user_message))
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | `DefenderRtpClient` | The Defender client |
| `resolve_call` | `Callable[[AgentContext], A365DefenderCall \| None \| Awaitable[...]]` | The agent identity and token resolver for a context. Called only for the points Defender evaluates while enabled; `None` (no agent identity) follows the fail mode |
| `on_evaluated` | `Callable[[DefenderRtpEvaluationResult], None] \| None` | Receives each evaluation (logging, telemetry) on a worker thread once the verdict is decided, outside the emitter's interceptor timeout; neither its exceptions (logged) nor its duration change the verdict |

`to_verdict(result)` maps a `DefenderRtpEvaluationResult` to an agent-hooks `Verdict`:

- evaluated `allow` of content within the limit: `allow` with Defender's warnings and `result_labels`; a warning
  reason that is empty or in the `host_error:` namespace (reserved by agent-hooks, whose emitter would reject the
  verdict and deny) becomes `defender:warning`
- evaluated `deny` or `transform` (also of a truncated copy): `deny`, reason `defender:block[:<reason>]`, the block reason as the message, the
  labels, and evidence pointing at `urn:a365:defender:<correlation id>`
- not evaluated, or an allow of a truncated copy (content over the limit, or the called tool's declaration cut or not
  among the first 10,000; `verified` false): `allow` with a
  `defender:unverified` warning (fail open), or `deny` with reason `runtime_error:defender_unverified` (fail closed)

An exception from the call resolver, the token resolver or the client (an invalid context or identity), or a call
resolver that returns `None`, is never a verdict: the interceptor turns it into `DefenderRtpClient.unavailable(...)`,
which follows the fail mode and reaches `on_evaluated`, rather than letting the emitter record a host error or
allowing the context unevaluated. Only the exception's type reaches the result (`evaluation failed (<type>)`), and
so the verdict and the interception record, since its message can carry credentials or content; the exception
itself is logged.

### A365PurviewInterceptor

An agent-hooks interceptor (`intercept(context) -> Verdict`, async), registered under the name `purview`.

```python
from microsoft_agents_a365.tooling.extensions.agenthooks import (
    A365PurviewCall,
    A365PurviewInterceptor,
    add_a365_purview,
    create_protection_emitter,
)

emitter = add_a365_purview(
    create_protection_emitter(defender=defender.options, purview=purview.options),
    A365PurviewInterceptor(purview, lambda context: A365PurviewCall(agent, graph_tokens), on_evaluated),
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | `PurviewDlpClient` | The Purview client |
| `resolve_call` | `Callable[[AgentContext], A365PurviewCall \| None \| Awaitable[...]]` | The agent and Graph token resolver for a context. Called only for content with text at `input` and `output` while enabled; `None` (no agent identity) follows the fail mode |
| `on_evaluated` | `Callable[[PurviewDlpEvaluationResult], None] \| None` | Receives each evaluation, reply audits included, on a worker thread once the verdict is decided; neither its exceptions (logged) nor its duration change the verdict |

Points and activities:

- `input`: the user's message (`input.content`) as `uploadText`, awaited.
- `output`: the reply (`output.content`) as `downloadText`. In the `audit` response mode (default) the interceptor
  starts the evaluation as a task of its own and allows at once: the task is kept in a set (strong reference), bounded
  by the client timeout plus two seconds (so the client's deadline applies first and the result keeps its
  `client-request-id`), never cancelled by the emitter, and its exceptions are retrieved and logged; its result goes
  to `on_evaluated`. `wait_for_pending_audits()` waits for the audits in flight. In `enforce` it is awaited and
  mapped like `input`.
- Other points, and content without text, are allowed without a call. A string is sent as it is; structured content
  as its string and number values in order, one per line (each container read once), kept only until the text is
  past twice the limit, a long value cut where needed so the work stays bounded, so the client always has more than
  the limit to cut and flag as truncated (a normalized character takes at most two of the original). When the text
  read is blank but the content goes on, Purview is not called and the fail mode applies: the rest was never read.
- The context's `session.id` (required: a context without one follows the fail mode) and `sequence` become the
  entry's `correlationId` and `sequenceNumber`, and its `agent.name` names the agent when the
  `PurviewDlpAgentContext` has no `agent_name`.

`to_verdict(result)` maps a `PurviewDlpEvaluationResult` to an agent-hooks `Verdict`:

- evaluated block (also of truncated content): `deny`, reason `purview:block`, the result's `block_reason` ("The
  request was blocked ..." at `input`, "The response was blocked ..." at `output`), and evidence pointing at
  `urn:a365:purview:<client-request-id>`
- evaluated allow of content within the limit: `allow`
- not evaluated, or an allow of truncated content (`verified` false): `allow` with a `purview:unverified` warning (fail
  open), or `deny` with reason `runtime_error:purview_unverified` (fail closed)

As for Defender, an exception from the call resolver, the token resolver or the client, or a call resolver that
returns `None`, becomes `PurviewDlpClient.unavailable(...)`, which follows the fail mode and reaches `on_evaluated`;
only the exception's type reaches the result.

### create_protection_emitter / add_a365_defender / add_a365_purview

`create_protection_emitter(interceptor_timeout_seconds=None, defender=None, purview=None)` returns an
`InterceptionEmitter` in enforce mode with the `parallel/strictest` profile, so Defender and Purview registered on one
emitter compose and a deny from either wins. The per-interceptor timeout defaults to the Defender timeout (the Defender
default when no Defender options are given) plus two seconds; when the Purview options are enabled, to the slower of
the Defender and Purview timeouts plus two seconds, so a Defender-only emitter is unchanged (a disabled Purview client
makes no calls). An explicit timeout must exceed those client timeouts, or `ValueError` is raised. Each client bounds
token acquisition and its call by one deadline, its own timeout, so its fail mode applies before the emitter's timeout
(an emitter timeout is a deny, `host_error:interceptor_timeout`, whatever the fail mode). agent-hooks' own default
interceptor timeout is 5 seconds, below the clients' default of 10, so hosts that build their own emitter must set its
timeout above both. agent-hooks 0.1 dispatches the interceptors of a parallel profile serially (isolation, not
scheduling), so a point both evaluate takes the sum of their latencies.

`add_a365_defender(emitter, interceptor)` and `add_a365_purview(emitter, interceptor)` register the interceptors under
`defender` and `purview` and return the emitter.

### Flow

```
Host (agent-hooks emitter)
       │  AgentContext at input / pre_tool_call / post_tool_call / output
       ▼
A365DefenderInterceptor.intercept()
       │  resolve_call(context) → A365DefenderCall(agent, token_resolver)   (None: unavailable, fail mode)
       ▼
DefenderRtpClient.evaluate_hook_context()          (microsoft-agents-a365-tooling)
       ├── fit a copy of the context to Defender's validation (normalize; envelope whole; content within the budget,
       │   the content under decision first; valid Unicode; agent's tenant; fill agent, actor)
       ├── token: cached, or token_resolver → agent identity app-only token (one deadline with the POST)
       └── POST endpoint (HTTPS), x-ms-correlation-id: <guid>
       ▼
DefenderRtpEvaluationResult → to_verdict() → agent-hooks Verdict
```

```
Host (agent-hooks emitter)
       │  AgentContext at input / output
       ▼
A365PurviewInterceptor.intercept()
       │  output in the audit response mode: background task, allow at once
       │  text of input.content / output.content: a string, or the string and number values, one per line
       │  (no text: allow; blank but not all read: unavailable, fail mode)
       │  resolve_call(context) → A365PurviewCall(agent, token_resolver)   (None: unavailable, fail mode)
       ▼
PurviewDlpClient.evaluate("uploadText" | "downloadText", text, agent, token_resolver)   (microsoft-agents-a365-tooling)
       ├── cut to max_content_characters (isTruncated), valid Unicode, conversation and sequence from the context
       ├── token: token_resolver → agentic user's delegated Graph token (/me), one deadline with the POST
       └── POST {graph}/me/dataSecurityAndGovernance/processContent (HTTPS), one new id as the client-request-id
           and the entry's identifier
       ▼
PurviewDlpEvaluationResult → to_verdict() → agent-hooks Verdict   (audit: on_evaluated only)
```

## File Structure

```
microsoft_agents_a365/tooling/extensions/agenthooks/
├── __init__.py
├── a365_agent_hooks.py              # create_protection_emitter, add_a365_defender, add_a365_purview
├── a365_defender_interceptor.py     # A365DefenderInterceptor, A365DefenderCall
└── a365_purview_interceptor.py      # A365PurviewInterceptor, A365PurviewCall
```

## Dependencies

- `agent-hooks-sdk` - agent-hooks Python SDK (`agent_hooks`): emitter, context, verdict types
- `microsoft-agents-a365-tooling` - `DefenderRtpClient`, `PurviewDlpClient`, and their options, results and token
  resolvers

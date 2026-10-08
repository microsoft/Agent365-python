# Tooling Extensions - agent-hooks - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling-extensions-agenthooks` package.

## Overview

This extension plugs Microsoft Defender for AI real-time protection (Defender RTP) into hosts that implement the
[agent-hooks](https://github.com/responsibleai/agent-hooks) control contract (AGENT-HOOKS-0.1). The host emits an
agent-hooks context at each interception point; `A365DefenderInterceptor` posts it to Defender's prevention endpoint
through `DefenderRtpClient` (from `microsoft-agents-a365-tooling`) and returns Defender's verdict to the emitter.

The Defender client lives in the core tooling package and has no agent-hooks dependency. agent-hooks ships a native
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
| `on_evaluated` | `Callable[[DefenderRtpEvaluationResult], None] \| None` | Receives each evaluation (logging, telemetry); its exceptions are logged and never change the verdict |

`to_verdict(result)` maps a `DefenderRtpEvaluationResult` to an agent-hooks `Verdict`:

- evaluated `allow` of content within the limit: `allow` with Defender's warnings and `result_labels`
- evaluated `deny` or `transform` (also of a truncated copy): `deny`, reason `defender:block[:<reason>]`, the block reason as the message, the
  labels, and evidence pointing at `urn:a365:defender:<correlation id>`
- not evaluated, or an allow of a truncated copy (content over the limit, or the called tool's declaration cut or not
  among the first 10,000; `verified` false): `allow` with a
  `defender:unverified` warning (fail open), or `deny` with reason `runtime_error:defender_unverified` (fail closed)

An exception from the call resolver, the token resolver or the client (an invalid context or identity), or a call
resolver that returns `None`, is never a verdict: the interceptor turns it into `DefenderRtpClient.unavailable(...)`,
which follows the fail mode and reaches `on_evaluated`, rather than letting the emitter record a host error or
allowing the context unevaluated.

### create_protection_emitter / add_a365_defender

`create_protection_emitter(interceptor_timeout_seconds=None, defender=None)` returns an `InterceptionEmitter` in
enforce mode with the `parallel/strictest` profile. The per-interceptor timeout defaults to the Defender timeout plus
two seconds. The client bounds token acquisition and the call by one deadline, the Defender timeout, so its fail mode
applies before the emitter's timeout (an emitter timeout is a deny, `host_error:interceptor_timeout`, whatever the
fail mode). agent-hooks' own default interceptor timeout is 5 seconds, below the client's default of 10, so hosts that
build their own emitter must set its timeout above the Defender timeout.

`add_a365_defender(emitter, interceptor)` registers the interceptor under `defender` and returns the emitter.

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

## File Structure

```
microsoft_agents_a365/tooling/extensions/agenthooks/
├── __init__.py
├── a365_agent_hooks.py              # create_protection_emitter, add_a365_defender
└── a365_defender_interceptor.py     # A365DefenderInterceptor, A365DefenderCall
```

## Dependencies

- `agent-hooks-sdk` - agent-hooks Python SDK (`agent_hooks`): emitter, context, verdict types
- `microsoft-agents-a365-tooling` - `DefenderRtpClient` and its options, results and token resolvers

# Microsoft Agent 365 Observability Hosting Library

This library provides hosting components for Agent 365 observability.

## Installation

```bash
pip install microsoft-agents-a365-observability-hosting
```

## App-only OBS token cache

Agent 365 observability export is S2S-only. Use
`AgenticTokenCache.refresh_observability_token(agent_id, tenant_id, token_resolver)`
from the exporter token resolver to acquire and cache an app-only OBS token for
the exporting agent identity.

```python
from microsoft_agents_a365.observability.hosting.token_cache_helpers import AgenticTokenCache

cache = AgenticTokenCache()


async def acquire_app_only_obs_token(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
    # Acquire a final app-only OBS token for agent_id and tenant_id.
    ...


async def token_resolver(agent_id: str, tenant_id: str) -> str:
    return await cache.refresh_observability_token(agent_id, tenant_id, acquire_app_only_obs_token)
```

The resolver receives the OBS `/.default` scope and must not perform user_fic or
OBO authentication. For blueprint-backed agents, acquire the final agent
identity app-only token before returning it; do not return the intermediate
blueprint assertion or a delegated workload token. The cache retries transient
acquisition failures, isolates entries by `(agent_id, tenant_id)`, respects JWT
expiry with refresh skew, and uses a fallback TTL for opaque tokens.

If you use an async exporter resolver, `_Agent365Exporter` runs it with
`asyncio.run` on the thread that performs the export:

- Scheduled batch exports and the final export during `shutdown()` run on the
  BatchSpanProcessor worker thread. `shutdown()` still blocks its caller until
  that export finishes.
- `force_flush()` exports on the calling thread. If you call it from inside a
  running event loop, the async resolver can't be awaited and that export
  fails with a logged error.

Create async clients inside the resolver; don't reuse `aiohttp` or
`azure.identity.aio` clients bound to your app's event loop. From async code,
call `force_flush()` and `shutdown()` with `await asyncio.to_thread(...)`. A
synchronous, thread-safe cached resolver avoids these event-loop restrictions
and is the pattern the Agent365-Samples Python samples use.
Call `refresh_observability_token` only from the exporter's `token_resolver`;
its per-key locks are `asyncio.Lock`s, so do not also refresh the same cache
instance from your app's own event loop or threads.

The previous delegated registration shape using `TurnContext` and
`Authorization.exchange_token` is removed for OBS export. `register_observability(...)`
is accepted only as a no-op compatibility shape: the cache logs once, stores no
token, and never calls `exchange_token`.

Token resolvers should validate returned tokens before caching: reject any `scp`
claim and any `idtyp` other than `app`; when `idtyp` is absent, accept only a
non-empty `roles` array or a non-empty `oid` equal to `sub`; also verify `aud`
is the OBS resource (`9b975845-388f-4429-889e-eab1ef63949c`) and the token is
not expired.

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
the exporting agent identity. `RefreshObservabilityToken(...)` is also available
as a compatibility alias.

```python
from microsoft_agents_a365.observability.hosting import AgenticTokenCache

cache = AgenticTokenCache()


async def refresh_app_only_obs(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
    # Acquire a final app-only OBS token for agent_id and tenant_id.
    ...


async def resolver(agent_id: str, tenant_id: str) -> str | None:
    await cache.refresh_observability_token(agent_id, tenant_id, refresh_app_only_obs)
    return cache.get_observability_token(agent_id, tenant_id)
```

The resolver receives the OBS `/.default` scope and must not perform user_fic or
OBO authentication. For blueprint-backed agents, acquire the final agent
identity app-only token before returning it; do not return the intermediate
blueprint assertion or a delegated workload token. The cache retries transient
acquisition failures, isolates entries by `(agent_id, tenant_id)`, respects JWT
expiry with refresh skew, and uses a fallback TTL for opaque tokens.

The previous delegated registration/refresh shapes using `TurnContext` and
`Authorization.exchange_token` are removed for OBS export. They are accepted only
as no-op compatibility shapes: the cache logs once, returns `None`, and never
calls `exchange_token`.

Token resolvers should validate returned tokens before caching: reject any `scp`
claim and any `idtyp` other than `app`; when `idtyp` is absent, accept only a
non-empty `roles` array or a non-empty `oid` equal to `sub`; also verify `aud`
is the OBS resource (`9b975845-388f-4429-889e-eab1ef63949c`) and the token is
not expired.

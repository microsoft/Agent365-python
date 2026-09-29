# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for AgenticTokenCache app-only OBS token handling."""

import asyncio
import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from microsoft_agents.hosting.core.app.oauth.authorization import Authorization
from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.observability.hosting.token_cache_helpers import (
    AgenticTokenCache,
    AgenticTokenStruct,
)


class StatusError(Exception):
    """Exception with an HTTP-like status code."""

    def __init__(self, status: int) -> None:
        super().__init__(f"status {status}")
        self.status = status


def _encode_segment(value: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(value).encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")


def make_jwt(exp_seconds_from_now: int, claims: dict[str, object] | None = None) -> str:
    """Create an unsigned JWT-like token for cache expiry tests."""
    payload = {
        "exp": int(time.time()) + exp_seconds_from_now,
        "idtyp": "app",
    }
    if claims is not None:
        payload.update(claims)
    return f"{_encode_segment({'alg': 'none'})}.{_encode_segment(payload)}.sig"


@pytest.fixture
def mock_authorization():
    """Create a mock Authorization instance."""
    auth = MagicMock(spec=Authorization)
    auth.exchange_token = AsyncMock()
    return auth


@pytest.fixture
def mock_turn_context():
    """Create a mock TurnContext instance."""
    return MagicMock(spec=TurnContext)


@pytest.fixture
def token_cache():
    """Create a fresh AgenticTokenCache instance."""
    return AgenticTokenCache()


@pytest.mark.asyncio
async def test_get_observability_token_returns_none_without_entry(token_cache):
    """A cache miss returns None."""
    assert await token_cache.get_observability_token("agent", "tenant") is None


@pytest.mark.asyncio
async def test_refresh_passes_identity_and_default_app_only_scope(token_cache):
    """Refresh calls the resolver with exporting identity and OBS /.default scope."""
    token = make_jwt(300, {"roles": []})
    calls = []

    def resolver(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
        calls.append((agent_id, tenant_id, scopes))
        return token

    refreshed = await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert refreshed == token
    assert await token_cache.get_observability_token("agent", "tenant") == token
    assert calls == [("agent", "tenant", ["api://9b975845-388f-4429-889e-eab1ef63949c/.default"])]


@pytest.mark.asyncio
async def test_refresh_uses_custom_app_only_scopes():
    """Constructor-provided scopes are passed through to the resolver."""
    token_cache = AgenticTokenCache(observability_scopes=["api://custom-obs/.default"])
    token = make_jwt(300)
    resolver = MagicMock(return_value=token)

    await token_cache.refresh_observability_token("agent", "tenant", resolver)

    resolver.assert_called_once_with("agent", "tenant", ["api://custom-obs/.default"])


@pytest.mark.asyncio
async def test_refresh_accepts_async_resolver(token_cache):
    """Async app-only resolvers are awaited by the hosting cache."""
    token = make_jwt(300)

    async def resolver(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
        await asyncio.sleep(0)
        return f"{agent_id}:{tenant_id}:{scopes[0]}:{token}"

    refreshed = await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert refreshed == (
        f"agent:tenant:api://9b975845-388f-4429-889e-eab1ef63949c/.default:{token}"
    )


@pytest.mark.asyncio
async def test_legacy_register_shape_logs_once_and_does_not_exchange(
    token_cache, mock_authorization, mock_turn_context, caplog
):
    """Removed delegated registration shape is a safe no-op."""
    token_struct = AgenticTokenStruct(
        authorization=mock_authorization,
        turn_context=mock_turn_context,
    )

    with caplog.at_level("ERROR"):
        token_cache.register_observability("agent", "tenant", token_struct, ["scope"])
        token_cache.register_observability("agent", "tenant", token_struct, ["scope"])

    mock_authorization.exchange_token.assert_not_called()
    assert await token_cache.get_observability_token("agent", "tenant") is None
    assert sum("Delegated OBS token" in record.message for record in caplog.records) == 1


@pytest.mark.asyncio
async def test_refresh_rejects_non_callable_resolver(token_cache):
    """refresh_observability_token requires a callable resolver."""
    with pytest.raises(TypeError, match="token_resolver must be callable"):
        await token_cache.refresh_observability_token("agent", "tenant", "not-callable")


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id,tenant_id", [("", "tenant"), ("agent", " ")])
async def test_refresh_rejects_empty_identity(token_cache, agent_id, tenant_id):
    """Agent and tenant IDs are required for app-only refresh."""
    resolver = MagicMock(return_value=make_jwt(300))

    with pytest.raises(ValueError, match="Agent and tenant IDs"):
        await token_cache.refresh_observability_token(agent_id, tenant_id, resolver)

    resolver.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_rejects_empty_scope_configuration():
    """An empty OBS scope configuration fails before token acquisition."""
    token_cache = AgenticTokenCache(observability_scopes=[])
    resolver = MagicMock(return_value=make_jwt(300))

    with pytest.raises(ValueError, match="No valid scopes"):
        await token_cache.refresh_observability_token("agent", "tenant", resolver)

    resolver.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "", " "])
async def test_refresh_surfaces_empty_resolver_result(token_cache, token):
    """Empty resolver results propagate as refresh failures."""
    resolver = MagicMock(return_value=token)

    with pytest.raises(RuntimeError, match="returned no token"):
        await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert await token_cache.get_observability_token("agent", "tenant") is None


@pytest.mark.asyncio
async def test_refresh_propagates_permanent_resolver_failure(token_cache):
    """Permanent acquisition errors clear stale cached tokens and propagate."""
    await token_cache.refresh_observability_token("agent", "tenant", lambda *_: make_jwt(300))
    error = RuntimeError("permission denied")
    resolver = MagicMock(side_effect=error)
    token_cache.invalidate_token("agent", "tenant")

    with pytest.raises(RuntimeError, match="permission denied"):
        await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert await token_cache.get_observability_token("agent", "tenant") is None


@pytest.mark.asyncio
async def test_refresh_retries_transient_failure_then_caches(token_cache, monkeypatch):
    """Transient resolver failures are retried before succeeding."""
    token = make_jwt(300)
    resolver = MagicMock(side_effect=[StatusError(503), token])

    async def no_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    refreshed = await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert refreshed == token
    assert resolver.call_count == 2
    assert await token_cache.get_observability_token("agent", "tenant") == token


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), ConnectionResetError()])
async def test_refresh_retries_standard_transient_exceptions(token_cache, monkeypatch, error):
    """Bare timeout and connection-reset errors are retried even without a message."""
    token = make_jwt(300)
    resolver = MagicMock(side_effect=[error, token])

    async def no_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    assert await token_cache.refresh_observability_token("agent", "tenant", resolver) == token
    assert resolver.call_count == 2


@pytest.mark.asyncio
async def test_refresh_deduplicates_concurrent_same_identity_acquisition(token_cache):
    """Concurrent refreshes for the same key share the first acquired token."""
    token = make_jwt(300)
    call_count = 0

    async def resolver(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0)
        return token

    results = await asyncio.gather(
        *(token_cache.refresh_observability_token("agent", "tenant", resolver) for _ in range(8))
    )

    assert results == [token] * 8
    assert call_count == 1


@pytest.mark.asyncio
async def test_refresh_reuses_cached_token_until_expiry_skew(token_cache):
    """A non-expired token is reused; near-expiry tokens are not returned."""
    token = make_jwt(120)
    resolver = MagicMock(return_value=token)

    await token_cache.refresh_observability_token("agent", "tenant", resolver)
    await token_cache.refresh_observability_token("agent", "tenant", resolver)

    assert resolver.call_count == 1
    assert await token_cache.get_observability_token("agent", "tenant") == token

    token_cache.invalidate_token("agent", "tenant")
    near_expiry = make_jwt(30)
    await token_cache.refresh_observability_token("agent", "tenant", lambda *_: near_expiry)
    assert await token_cache.get_observability_token("agent", "tenant") is None


@pytest.mark.asyncio
async def test_opaque_token_uses_fresh_fallback_ttl(token_cache):
    """Opaque tokens get a fallback TTL after replacing expired JWT metadata."""
    await token_cache.refresh_observability_token("agent", "tenant", lambda *_: make_jwt(120))
    token_cache.invalidate_token("agent", "tenant")
    await token_cache.refresh_observability_token("agent", "tenant", lambda *_: "opaque-token")

    assert await token_cache.get_observability_token("agent", "tenant") == "opaque-token"
    entry = token_cache._map[AgenticTokenCache._make_key("agent", "tenant")]
    entry.acquired_on_ms = (time.time() * 1000) - token_cache._default_max_token_age_ms - 1
    assert await token_cache.get_observability_token("agent", "tenant") is None


@pytest.mark.asyncio
async def test_tokens_are_isolated_by_agent_and_tenant(token_cache):
    """Agent and tenant are both part of the cache key."""

    def resolver(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
        return f"{agent_id}:{tenant_id}"

    await token_cache.refresh_observability_token("agent-one", "tenant-a", resolver)
    await token_cache.refresh_observability_token("agent-two", "tenant-a", resolver)
    await token_cache.refresh_observability_token("agent-one", "tenant-b", resolver)

    assert (
        await token_cache.get_observability_token("agent-one", "tenant-a") == "agent-one:tenant-a"
    )
    assert (
        await token_cache.get_observability_token("agent-two", "tenant-a") == "agent-two:tenant-a"
    )
    assert (
        await token_cache.get_observability_token("agent-one", "tenant-b") == "agent-one:tenant-b"
    )


@pytest.mark.asyncio
async def test_invalidate_one_then_all(token_cache):
    """Token invalidation is scoped by key or all keys."""
    token = make_jwt(300)
    await token_cache.refresh_observability_token("one", "tenant", lambda *_: token)
    await token_cache.refresh_observability_token("two", "tenant", lambda *_: token)

    token_cache.invalidate_token("one", "tenant")
    assert await token_cache.get_observability_token("one", "tenant") is None
    assert await token_cache.get_observability_token("two", "tenant") == token

    token_cache.invalidate_all()
    assert await token_cache.get_observability_token("two", "tenant") is None


@pytest.mark.asyncio
async def test_cache_evicts_oldest_entry_when_capacity_is_reached(token_cache):
    """Cache size is bounded and evicts the oldest key."""
    token_cache._max_cache_size = 2
    token = make_jwt(300)
    await token_cache.refresh_observability_token("one", "tenant", lambda *_: token)
    await token_cache.refresh_observability_token("two", "tenant", lambda *_: token)
    await token_cache.refresh_observability_token("three", "tenant", lambda *_: token)

    assert await token_cache.get_observability_token("one", "tenant") is None
    assert await token_cache.get_observability_token("two", "tenant") == token
    assert await token_cache.get_observability_token("three", "tenant") == token


@pytest.mark.asyncio
async def test_separator_bearing_ids_do_not_share_a_cache_entry(token_cache):
    """IDs that contain a separator character never alias another identity."""
    first = MagicMock(return_value="token-for-first")
    second = MagicMock(return_value="token-for-second")

    assert await token_cache.refresh_observability_token("a:b", "c", first) == "token-for-first"
    assert await token_cache.refresh_observability_token("a", "b:c", second) == "token-for-second"

    second.assert_called_once()
    assert await token_cache.get_observability_token("a:b", "c") == "token-for-first"
    assert await token_cache.get_observability_token("a", "b:c") == "token-for-second"


@pytest.mark.asyncio
async def test_identity_churn_keeps_every_per_identity_registry_bounded(token_cache):
    """Refresh locks live and die with cache entries, so identity churn stays bounded."""
    token_cache._max_cache_size = 2
    token = make_jwt(300)
    for agent_id in ("one", "two", "three", "four"):
        await token_cache.refresh_observability_token(agent_id, "tenant", lambda *_: token)

    registries = {
        name: len(value) for name, value in vars(token_cache).items() if isinstance(value, dict)
    }
    assert registries == {"_map": 2}

    token_cache.invalidate_all()
    registries = {
        name: len(value) for name, value in vars(token_cache).items() if isinstance(value, dict)
    }
    assert registries == {"_map": 0}


@pytest.mark.asyncio
async def test_eviction_keeps_in_flight_entry_then_trims_overflow(token_cache):
    """Eviction skips a refresh that is still running; the next insertion restores the bound."""
    token_cache._max_cache_size = 1
    release = asyncio.Event()

    async def slow_resolver(agent_id: str, tenant_id: str, scopes: list[str]) -> str:
        await release.wait()
        return "token-for-slow"

    in_flight = asyncio.create_task(
        token_cache.refresh_observability_token("slow", "tenant", slow_resolver)
    )
    await asyncio.sleep(0)
    fast = await token_cache.refresh_observability_token(
        "fast", "tenant", lambda *_: "token-for-fast"
    )

    release.set()
    assert fast == "token-for-fast"
    assert await in_flight == "token-for-slow"
    assert await token_cache.get_observability_token("slow", "tenant") == "token-for-slow"

    await token_cache.refresh_observability_token("next", "tenant", lambda *_: "token-for-next")
    assert len(token_cache._map) == 1

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for PurviewDlpTokenResolvers."""

from __future__ import annotations

import asyncio
import contextvars
import threading
from unittest.mock import AsyncMock

import pytest
from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpAgentContext,
    PurviewDlpToken,
    PurviewDlpTokenResolvers,
)

from .defender_fakes import create_token
from .purview_fakes import AGENT, AGENT_ID, AGENTIC_USER_ID, GRAPH_SCOPE, TENANT_ID

NOW = 1_800_000_000.0


def jwt(expires_at: float) -> str:
    """An unsigned JWT that expires at ``expires_at`` (seconds since the epoch)."""
    return create_token(exp=int(expires_at))


class AgenticConnection:
    """Stands in for an MSAL connection (hosting-core 0.8+): issues the agentic user's token."""

    def __init__(self, *tokens: object) -> None:
        self.tokens = list(tokens) or [jwt(NOW + 3600)]
        self.requests: list[tuple[str, str, str, list[str]]] = []
        self.gate: asyncio.Event | None = None

    async def get_agentic_user_token(
        self,
        tenant_id: str,
        agent_app_instance_id: str,
        agentic_user_id: str,
        scopes: list[str],
    ) -> object:
        self.requests.append((tenant_id, agent_app_instance_id, agentic_user_id, scopes))
        if self.gate is not None:
            await self.gate.wait()
        token = self.tokens.pop(0) if len(self.tokens) > 1 else self.tokens[0]
        if isinstance(token, Exception):
            raise token
        return token


class LegacyAgenticConnection:
    """The microsoft-agents-hosting-core 0.7 and earlier shape: the token takes no tenant."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, list[str]]] = []

    async def get_agentic_user_token(
        self, agent_app_instance_id: str, agentic_user_id: str, scopes: list[str]
    ) -> str | None:
        self.requests.append((agent_app_instance_id, agentic_user_id, scopes))
        return "agentic-user-token"


class Clock:
    def __init__(self, now: float = NOW) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


# ---- from_agentic_user -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issues_the_agentic_users_token_for_me() -> None:
    connection = AgenticConnection()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]

    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token == PurviewDlpToken(connection.tokens[0], None)
    assert connection.requests == [(TENANT_ID, AGENT_ID, AGENTIC_USER_ID, [GRAPH_SCOPE])]


@pytest.mark.asyncio
async def test_supports_connections_whose_user_token_takes_no_tenant() -> None:
    connection = LegacyAgenticConnection()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection)  # type: ignore[arg-type]

    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token == PurviewDlpToken("agentic-user-token")
    assert connection.requests == [(AGENT_ID, AGENTIC_USER_ID, [GRAPH_SCOPE])]


@pytest.mark.asyncio
async def test_passes_the_tenant_to_a_mocked_connection() -> None:
    connection = AsyncMock()
    connection.get_agentic_user_token.return_value = "agentic-user-token"
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection)

    await resolve(AGENT, [GRAPH_SCOPE])

    connection.get_agentic_user_token.assert_awaited_once_with(
        TENANT_ID, AGENT_ID, AGENTIC_USER_ID, [GRAPH_SCOPE]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent", "missing"),
    [
        (PurviewDlpAgentContext(AGENT_ID, TENANT_ID), "agentic_user_id"),
        (PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agentic_user_id=" "), "agentic_user_id"),
        (PurviewDlpAgentContext(AGENT_ID, "", agentic_user_id=AGENTIC_USER_ID), "tenant_id"),
        (PurviewDlpAgentContext("", TENANT_ID, agentic_user_id=AGENTIC_USER_ID), "agent_id"),
    ],
)
async def test_requires_the_agentic_user_and_the_agent(
    agent: PurviewDlpAgentContext, missing: str
) -> None:
    connection = AgenticConnection()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=f"{missing} is required"):
        await resolve(agent, [GRAPH_SCOPE])

    assert connection.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "", "  ", 5, {"token": "x"}])
async def test_raises_when_the_connection_returns_no_token(token: object) -> None:
    resolve = PurviewDlpTokenResolvers.from_agentic_user(AgenticConnection(token))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="no agentic user token"):
        await resolve(AGENT, [GRAPH_SCOPE])


@pytest.mark.asyncio
async def test_caches_the_token_per_agentic_user_and_scopes() -> None:
    connection = AgenticConnection()
    clock = Clock()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=clock)  # type: ignore[arg-type]
    other_user = PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agentic_user_id="other-user")

    await resolve(AGENT, [GRAPH_SCOPE])
    await resolve(AGENT, [GRAPH_SCOPE])
    await resolve(other_user, [GRAPH_SCOPE])
    await resolve(AGENT, ["https://graph.example.test/.default"])
    clock.now += 3600 - 301
    await resolve(AGENT, [GRAPH_SCOPE])

    assert [request[2:] for request in connection.requests] == [
        (AGENTIC_USER_ID, [GRAPH_SCOPE]),
        ("other-user", [GRAPH_SCOPE]),
        (AGENTIC_USER_ID, ["https://graph.example.test/.default"]),
    ]


@pytest.mark.asyncio
async def test_matches_cached_tokens_regardless_of_the_case_of_the_ids() -> None:
    connection = AgenticConnection()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]
    ids = ("aaaaaaaa-0000-0000-0000-00000000000a", "bbbbbbbb-0000-0000-0000-00000000000b")
    lower = PurviewDlpAgentContext(ids[0], ids[1], agentic_user_id="cccccccc-0000-0000-0000-0c")
    upper = PurviewDlpAgentContext(
        ids[0].upper(), ids[1].upper(), agentic_user_id="CCCCCCCC-0000-0000-0000-0C"
    )

    await resolve(lower, [GRAPH_SCOPE])
    await resolve(upper, [GRAPH_SCOPE])

    assert len(connection.requests) == 1


@pytest.mark.asyncio
async def test_shares_one_acquisition_between_concurrent_evaluations() -> None:
    connection = AgenticConnection()
    connection.gate = asyncio.Event()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]

    calls = [asyncio.ensure_future(resolve(AGENT, [GRAPH_SCOPE])) for _ in range(5)]
    await asyncio.sleep(0)
    connection.gate.set()
    tokens = await asyncio.gather(*calls)

    assert len(connection.requests) == 1
    assert len({token.access_token for token in tokens}) == 1


@pytest.mark.asyncio
async def test_never_caches_a_failure() -> None:
    connection = AgenticConnection(RuntimeError("AADSTS50000"), jwt(NOW + 3600))
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="AADSTS50000"):
        await resolve(AGENT, [GRAPH_SCOPE])
    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token.access_token == connection.tokens[0]
    assert len(connection.requests) == 2


@pytest.mark.asyncio
async def test_refreshes_ahead_of_expiry_and_keeps_the_cached_token_when_that_fails() -> None:
    first = jwt(NOW + 3600)
    connection = AgenticConnection(first, RuntimeError("Entra is down"), jwt(NOW + 7200))
    clock = Clock()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=clock)  # type: ignore[arg-type]
    await resolve(AGENT, [GRAPH_SCOPE])

    clock.now = NOW + 3600 - 60
    during_failed_refresh = await resolve(AGENT, [GRAPH_SCOPE])
    await asyncio.sleep(0.01)
    after_failed_refresh = await resolve(AGENT, [GRAPH_SCOPE])
    await asyncio.sleep(0.01)
    refreshed = await resolve(AGENT, [GRAPH_SCOPE])

    assert during_failed_refresh.access_token == first
    assert after_failed_refresh.access_token == first
    assert refreshed.access_token == connection.tokens[0]
    assert len(connection.requests) == 3


@pytest.mark.asyncio
async def test_waits_for_a_new_token_once_the_cached_one_expired() -> None:
    connection = AgenticConnection(jwt(NOW + 3600), jwt(NOW + 7200))
    clock = Clock()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=clock)  # type: ignore[arg-type]
    await resolve(AGENT, [GRAPH_SCOPE])

    clock.now = NOW + 3600
    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token.access_token == connection.tokens[0]
    assert len(connection.requests) == 2


@pytest.mark.asyncio
async def test_does_not_cache_a_token_without_an_expiry() -> None:
    connection = AgenticConnection("opaque-token")
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection)  # type: ignore[arg-type]

    await resolve(AGENT, [GRAPH_SCOPE])
    await resolve(AGENT, [GRAPH_SCOPE])

    assert len(connection.requests) == 2


@pytest.mark.asyncio
async def test_rejects_an_expired_token() -> None:
    resolve = PurviewDlpTokenResolvers.from_agentic_user(
        AgenticConnection(jwt(NOW - 1)),  # type: ignore[arg-type]
        clock=Clock(),
    )

    with pytest.raises(RuntimeError, match="expired"):
        await resolve(AGENT, [GRAPH_SCOPE])


@pytest.mark.asyncio
async def test_bounds_each_acquisition_and_retries_after_it_times_out() -> None:
    connection = AgenticConnection()
    connection.gate = asyncio.Event()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(
        connection,  # type: ignore[arg-type]
        timeout_seconds=0.05,
        clock=Clock(),
    )

    with pytest.raises(TimeoutError):
        await resolve(AGENT, [GRAPH_SCOPE])
    connection.gate.set()
    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token.access_token == connection.tokens[0]
    assert len(connection.requests) == 2


@pytest.mark.asyncio
async def test_an_acquisition_outlives_a_callers_deadline_and_is_cached() -> None:
    connection = AgenticConnection()
    connection.gate = asyncio.Event()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(resolve(AGENT, [GRAPH_SCOPE]), timeout=0.05)
    connection.gate.set()
    await asyncio.sleep(0.01)
    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token.access_token == connection.tokens[0]
    assert len(connection.requests) == 1


@pytest.mark.asyncio
async def test_keeps_at_most_100_tokens() -> None:
    connection = AgenticConnection()
    resolve = PurviewDlpTokenResolvers.from_agentic_user(connection, clock=Clock())  # type: ignore[arg-type]

    def user(index: int) -> PurviewDlpAgentContext:
        return PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agentic_user_id=f"user-{index}")

    for index in range(101):
        await resolve(user(index), [GRAPH_SCOPE])
    await resolve(user(100), [GRAPH_SCOPE])
    assert len(connection.requests) == 101, "the newest token is cached"

    await resolve(user(0), [GRAPH_SCOPE])
    assert len(connection.requests) == 102, "the oldest one made room for it"


@pytest.mark.parametrize("timeout", [0, -1.0, float("nan"), float("inf"), True])
def test_requires_a_positive_finite_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        PurviewDlpTokenResolvers.from_agentic_user(AgenticConnection(), timeout_seconds=timeout)  # type: ignore[arg-type]


def test_requires_a_connection() -> None:
    with pytest.raises(TypeError, match="connection"):
        PurviewDlpTokenResolvers.from_agentic_user(None)  # type: ignore[arg-type]


# ---- from_access_token_provider --------------------------------------------------------------


@pytest.mark.asyncio
async def test_uses_an_async_host_token_for_me() -> None:
    requests: list[list[str]] = []

    async def get_token(scopes: list[str]) -> str:
        requests.append(scopes)
        return "host-token"

    resolve = PurviewDlpTokenResolvers.from_access_token_provider(get_token)

    assert await resolve(AGENT, [GRAPH_SCOPE]) == PurviewDlpToken("host-token")
    assert requests == [[GRAPH_SCOPE]]


@pytest.mark.asyncio
async def test_runs_a_synchronous_host_provider_off_the_event_loop_in_the_callers_context() -> None:
    user = contextvars.ContextVar("user", default="nobody")
    loop_thread = threading.get_ident()
    seen: list[tuple[int, str]] = []

    def get_token(_scopes: list[str]) -> str:
        seen.append((threading.get_ident(), user.get()))
        return "app-token"

    resolve = PurviewDlpTokenResolvers.from_access_token_provider(get_token, user_id="user-1")
    user.set("signed-in-user")

    token = await resolve(AGENT, [GRAPH_SCOPE])

    assert token == PurviewDlpToken("app-token", "user-1")
    ((thread, current_user),) = seen
    assert thread != loop_thread
    assert current_user == "signed-in-user"


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "", " ", 7])
async def test_raises_when_the_host_provider_returns_no_token(token: object) -> None:
    resolve = PurviewDlpTokenResolvers.from_access_token_provider(lambda _scopes: token)  # type: ignore[arg-type,return-value]

    with pytest.raises(RuntimeError, match="returned no token"):
        await resolve(AGENT, [GRAPH_SCOPE])


@pytest.mark.parametrize("user_id", ["", "  "])
def test_rejects_an_empty_user_id(user_id: str) -> None:
    with pytest.raises(ValueError, match="user_id"):
        PurviewDlpTokenResolvers.from_access_token_provider(lambda _scopes: "t", user_id=user_id)


def test_requires_a_callable_provider() -> None:
    with pytest.raises(TypeError, match="get_token"):
        PurviewDlpTokenResolvers.from_access_token_provider("token")  # type: ignore[arg-type]

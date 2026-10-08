# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for DefenderRtpTokenResolvers.from_agentic_connection."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import aiohttp
import pytest
from microsoft_agents_a365.tooling.protection.defender import (
    DEFAULT_AUTHENTICATION_SCOPE,
    DefenderRtpTokenResolvers,
)

from .defender_fakes import (
    AGENT_ID,
    TENANT_ID,
    FakeResponse,
    FakeTokenSession,
    json_response,
    text_response,
)

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"


class FakeAgenticConnection:
    """Stands in for an MSAL connection: returns the agent identity's FMI assertion."""

    def __init__(self, assertion: str | None = "agent-identity-assertion") -> None:
        self.assertion = assertion
        self.requests: list[tuple[str, str]] = []

    async def get_agentic_application_token(
        self, tenant_id: str, agent_app_instance_id: str
    ) -> str | None:
        self.requests.append((tenant_id, agent_app_instance_id))
        return self.assertion


class LegacyAgenticConnection:
    """The microsoft-agents-hosting-core 0.7 shape: the assertion takes no tenant."""

    def __init__(self) -> None:
        self.requests: list[str] = []

    async def get_agentic_application_token(self, agent_app_instance_id: str) -> str | None:
        self.requests.append(agent_app_instance_id)
        return "agent-identity-assertion"


@pytest.mark.asyncio
async def test_exchanges_the_agent_identity_assertion_for_the_defender_token() -> None:
    connection = FakeAgenticConnection()
    session = FakeTokenSession()
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(connection, session)  # type: ignore[arg-type]

    token = await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])

    assert token == "defender-token"
    assert connection.requests == [(TENANT_ID, AGENT_ID)]
    assert session.requests == [
        (
            TOKEN_URL,
            {
                "grant_type": "client_credentials",
                "client_id": AGENT_ID,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": "agent-identity-assertion",
                "scope": DEFAULT_AUTHENTICATION_SCOPE,
            },
        )
    ]
    assert session.pending[0].response is not None and session.pending[0].response.exited
    assert not session.closed


@pytest.mark.asyncio
async def test_supports_connections_whose_assertion_takes_no_tenant() -> None:
    connection = LegacyAgenticConnection()
    session = FakeTokenSession()
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(connection, session)  # type: ignore[arg-type]

    token = await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])

    assert token == "defender-token"
    assert connection.requests == [AGENT_ID]
    ((url, form),) = session.requests
    assert url == TOKEN_URL
    assert form["client_id"] == AGENT_ID


@pytest.mark.asyncio
async def test_passes_the_tenant_to_a_mocked_connection() -> None:
    connection = AsyncMock()
    connection.get_agentic_application_token.return_value = "agent-identity-assertion"
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(connection, FakeTokenSession())  # type: ignore[arg-type]

    await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])

    connection.get_agentic_application_token.assert_awaited_once_with(TENANT_ID, AGENT_ID)


@pytest.mark.asyncio
async def test_uses_the_authority_and_escapes_the_tenant() -> None:
    session = FakeTokenSession()
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(
        FakeAgenticConnection(),  # type: ignore[arg-type]
        session,  # type: ignore[arg-type]
        authority="https://login.example.test/",
    )

    await resolve(AGENT_ID, "contoso tenant/x", ["scope-a", "scope-b"])

    ((url, form),) = session.requests
    assert url == "https://login.example.test/contoso%20tenant%2Fx/oauth2/v2.0/token"
    assert form["scope"] == "scope-a scope-b"


@pytest.mark.asyncio
async def test_raises_without_the_response_body_when_the_token_request_fails() -> None:
    session = FakeTokenSession(
        lambda: json_response(
            {"error": "invalid_client", "error_description": "echoes agent-identity-assertion"},
            status=401,
        )
    )
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(FakeAgenticConnection(), session)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as raised:
        await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])

    assert str(raised.value) == "The Defender token request failed with HTTP 401."
    assert "assertion" not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        json_response({"token_type": "Bearer"}),
        json_response({"access_token": ""}),
        json_response(["not", "an", "object"]),
        text_response("<html>not json</html>"),
    ],
)
async def test_raises_when_the_token_response_has_no_access_token(response: FakeResponse) -> None:
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(
        FakeAgenticConnection(),  # type: ignore[arg-type]
        FakeTokenSession(lambda: response),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="no access_token"):
        await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])


@pytest.mark.asyncio
async def test_raises_without_a_token_request_when_the_connection_returns_no_assertion() -> None:
    session = FakeTokenSession()
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(
        FakeAgenticConnection(assertion=None),  # type: ignore[arg-type]
        session,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="no agent identity assertion"):
        await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE])

    assert session.requests == []


@pytest.mark.asyncio
async def test_cancellation_stops_the_token_request() -> None:
    entered = asyncio.Event()

    async def hanging() -> FakeResponse:
        entered.set()
        await asyncio.sleep(5)
        return json_response({"access_token": "late"})

    session = FakeTokenSession(hanging)
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(FakeAgenticConnection(), session)  # type: ignore[arg-type]
    request = asyncio.ensure_future(resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE]))
    await asyncio.wait_for(entered.wait(), timeout=1)

    request.cancel()

    with pytest.raises(asyncio.CancelledError):
        await request
    assert len(session.requests) == 1
    assert session.pending[0].response is None


@pytest.mark.asyncio
async def test_opens_and_closes_its_own_session_when_none_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions: list[FakeTokenSession] = []

    class OwnedSession(FakeTokenSession):
        async def __aenter__(self) -> OwnedSession:
            sessions.append(self)
            return self

        async def __aexit__(self, *_exc: object) -> None:
            self.closed = True

    monkeypatch.setattr(aiohttp, "ClientSession", OwnedSession)
    resolve = DefenderRtpTokenResolvers.from_agentic_connection(FakeAgenticConnection())  # type: ignore[arg-type]

    assert await resolve(AGENT_ID, TENANT_ID, [DEFAULT_AUTHENTICATION_SCOPE]) == "defender-token"
    (session,) = sessions
    assert session.closed


@pytest.mark.parametrize(
    "authority",
    ["http://login.microsoftonline.com", "login.microsoftonline.com", "/oauth2", ""],
)
def test_requires_an_absolute_https_authority(authority: str) -> None:
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        DefenderRtpTokenResolvers.from_agentic_connection(
            FakeAgenticConnection(),  # type: ignore[arg-type]
            authority=authority,
        )


def test_requires_a_connection() -> None:
    with pytest.raises(TypeError, match="connection"):
        DefenderRtpTokenResolvers.from_agentic_connection(None)  # type: ignore[arg-type]

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fakes for the Microsoft Graph processContent API and the agentic user's token."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpAgentContext,
    PurviewDlpToken,
)

from .defender_fakes import FakeResponse, JsonObject, create_token, json_response

AGENT_ID = "33333333-3333-3333-3333-333333333333"
TENANT_ID = "22222222-2222-2222-2222-222222222222"
AGENTIC_USER_ID = "44444444-4444-4444-4444-444444444444"
BLUEPRINT_ID = "55555555-5555-5555-5555-555555555555"
GRAPH_BASE_URL = "https://graph.example.test/v1.0"
ME_URL = f"{GRAPH_BASE_URL}/me/dataSecurityAndGovernance/processContent"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

CLEAN = {"protectionScopeState": "modified", "policyActions": [], "processingErrors": []}
BLOCK = {
    "protectionScopeState": "modified",
    "policyActions": [
        {
            "@odata.type": "#microsoft.graph.restrictAccessAction",
            "action": "restrictAccess",
            "restrictionAction": "block",
        }
    ],
    "processingErrors": [],
}

AGENT = PurviewDlpAgentContext(
    agent_id=AGENT_ID,
    tenant_id=TENANT_ID,
    agentic_user_id=AGENTIC_USER_ID,
    blueprint_id=BLUEPRINT_ID,
    agent_name="SampleAgent",
)

GraphResponder = Callable[[JsonObject], FakeResponse | Awaitable[FakeResponse]]


def clean(_body: JsonObject) -> FakeResponse:
    """Purview found nothing to act on."""
    return json_response(CLEAN)


def block(_body: JsonObject) -> FakeResponse:
    """A DLP policy blocks the content."""
    return json_response(BLOCK)


def block_card_numbers(body: JsonObject) -> FakeResponse:
    """Blocks uploaded text that contains a card number, like a credit card DLP policy."""
    if activity_of(body) == "uploadText" and "4111" in text_of(body):
        return json_response(BLOCK)
    return json_response(CLEAN)


def entry_of(body: JsonObject) -> JsonObject:
    """The request's single content entry."""
    (entry,) = body["contentToProcess"]["contentEntries"]  # type: ignore[index]
    return entry  # type: ignore[no-any-return]


def text_of(body: JsonObject) -> str:
    """The text a request sends."""
    return entry_of(body)["content"]["data"]  # type: ignore[index,no-any-return]


def activity_of(body: JsonObject) -> str:
    """The activity a request evaluates."""
    return body["contentToProcess"]["activityMetadata"]["activity"]  # type: ignore[index,no-any-return]


@dataclass(frozen=True)
class RecordedGraphCall:
    """One request the fake processContent API received."""

    url: str
    authorization: str | None
    client_request_id: str | None
    content_type: str | None
    body: JsonObject
    allow_redirects: bool = True


class _PendingRequest:
    def __init__(self, respond: Callable[[], Awaitable[FakeResponse]]) -> None:
        self._respond = respond
        self.response: FakeResponse | None = None

    async def __aenter__(self) -> FakeResponse:
        self.response = await self._respond()
        return self.response

    async def __aexit__(self, *_exc: object) -> None:
        if self.response is not None:
            self.response.exited = True


class FakeGraphSession:
    """Stands in for the ``aiohttp.ClientSession`` the client posts with.

    Records each request and answers with ``respond(body)``, like a fake HTTP handler.
    """

    def __init__(self, respond: GraphResponder = clean) -> None:
        self.respond = respond
        self.calls: list[RecordedGraphCall] = []

    @property
    def bodies(self) -> list[JsonObject]:
        """The request bodies, in order."""
        return [call.body for call in self.calls]

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: Mapping[str, str],
        allow_redirects: bool = True,
    ) -> _PendingRequest:
        async def respond() -> FakeResponse:
            body = json.loads(data)
            self.calls.append(
                RecordedGraphCall(
                    url=url,
                    authorization=headers.get("Authorization"),
                    client_request_id=headers.get("client-request-id"),
                    content_type=headers.get("Content-Type"),
                    body=body,
                    allow_redirects=allow_redirects,
                )
            )
            response = self.respond(body)
            return await response if inspect.isawaitable(response) else response

        return _PendingRequest(respond)


class GraphTokens:
    """Resolves a delegated Graph token for ``/me`` and records each request."""

    def __init__(self, token: str | None = None, user_id: str | None = None) -> None:
        self.token = token or create_token(scp="Content.Process.User")
        self.user_id = user_id
        self.requests: list[tuple[PurviewDlpAgentContext, list[str]]] = []

    async def resolve(self, agent: PurviewDlpAgentContext, scopes: list[str]) -> PurviewDlpToken:
        self.requests.append((agent, scopes))
        return PurviewDlpToken(self.token, self.user_id)

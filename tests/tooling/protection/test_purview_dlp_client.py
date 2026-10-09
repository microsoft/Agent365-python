# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for PurviewDlpClient against a fake Microsoft Graph processContent API."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
import time
import uuid
from datetime import UTC, datetime

import aiohttp
import pytest
from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpAgentContext,
    PurviewDlpClient,
    PurviewDlpDecision,
    PurviewDlpEvaluationResult,
    PurviewDlpOptions,
    PurviewDlpToken,
)

from .defender_fakes import FakeResponse, JsonObject, json_response, text_response
from .purview_fakes import (
    AGENT,
    AGENT_ID,
    AGENTIC_USER_ID,
    BLUEPRINT_ID,
    CLEAN,
    GRAPH_BASE_URL,
    GRAPH_SCOPE,
    ME_URL,
    TENANT_ID,
    FakeGraphSession,
    GraphResponder,
    GraphTokens,
    block,
    clean,
    entry_of,
)

FIXED_NOW = datetime(2026, 10, 7, 10, 0, 0, 250000, tzinfo=UTC).timestamp()
TRUNCATED_ERROR = "content exceeded max_content_characters; Purview evaluated a truncated copy"


def make_client(
    respond: GraphResponder = clean,
    **options: object,
) -> tuple[PurviewDlpClient, FakeGraphSession]:
    session = FakeGraphSession(respond)
    settings = {"enabled": True, "graph_base_url": GRAPH_BASE_URL, **options}
    client = PurviewDlpClient(
        PurviewDlpOptions(**settings),  # type: ignore[arg-type]
        session,  # type: ignore[arg-type]
        clock=lambda: FIXED_NOW,
    )
    return client, session


async def evaluate(
    client: PurviewDlpClient,
    text: str = "Find 2 flights from Seattle to San Francisco next week",
    activity: str = "uploadText",
    tokens: GraphTokens | None = None,
    **kwargs: object,
) -> PurviewDlpEvaluationResult:
    result = await client.evaluate(
        activity,  # type: ignore[arg-type]
        text,
        AGENT,
        (tokens or GraphTokens()).resolve,
        session_id="conversation-1",
        **kwargs,  # type: ignore[arg-type]
    )
    assert result is not None
    return result


# ---- request ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_posts_an_upload_text_request_as_the_agentic_user() -> None:
    client, graph = make_client()
    tokens = GraphTokens()

    result = await evaluate(client, "Book the hotel", tokens=tokens, sequence_number=3)

    assert result.allowed is True
    assert result.evaluated is True
    assert result.verified is True
    assert result.activity == "uploadText"
    assert result.http_status == 200
    assert result.protection_scope_state == "modified"
    assert result.decision == PurviewDlpDecision()
    assert result.error is None
    (call,) = graph.calls
    assert call.url == ME_URL
    assert call.authorization == f"Bearer {tokens.token}"
    assert call.content_type == "application/json"
    assert call.allow_redirects is False
    assert call.client_request_id == result.correlation_id
    assert str(uuid.UUID(result.correlation_id)) == result.correlation_id
    assert tokens.requests == [(AGENT, [GRAPH_SCOPE])]
    assert call.body == {
        "contentToProcess": {
            "contentEntries": [
                {
                    "@odata.type": "microsoft.graph.processConversationMetadata",
                    "identifier": result.correlation_id,
                    "content": {
                        "@odata.type": "microsoft.graph.textContent",
                        "data": "Book the hotel",
                    },
                    "name": "SampleAgent uploadText",
                    "correlationId": "conversation-1",
                    "sequenceNumber": 3,
                    "isTruncated": False,
                    "createdDateTime": "2026-10-07T10:00:00.250Z",
                    "modifiedDateTime": "2026-10-07T10:00:00.250Z",
                    "contentCategory": "ai",
                    "agents": [
                        {
                            "@odata.type": "microsoft.graph.aiAgentInfo",
                            "blueprintId": BLUEPRINT_ID,
                            "identifier": AGENT_ID,
                            "name": "SampleAgent",
                            "version": "1.0",
                        }
                    ],
                }
            ],
            "activityMetadata": {"activity": "uploadText"},
            "integratedAppMetadata": {"name": "SampleAgent", "version": "1.0"},
            "protectedAppMetadata": {
                "name": "SampleAgent",
                "version": "1.0",
                "applicationLocation": {
                    "@odata.type": "microsoft.graph.policyLocationApplication",
                    "value": BLUEPRINT_ID,
                },
            },
        }
    }


@pytest.mark.asyncio
async def test_posts_a_download_text_request_for_the_reply() -> None:
    client, graph = make_client()

    result = await evaluate(client, "Here are two flights.", activity="downloadText")

    assert result.activity == "downloadText"
    (body,) = graph.bodies
    assert body["contentToProcess"]["activityMetadata"] == {"activity": "downloadText"}  # type: ignore[index]
    assert entry_of(body)["name"] == "SampleAgent downloadText"


@pytest.mark.asyncio
async def test_sends_one_new_id_per_call_as_client_request_id_and_entry_identifier() -> None:
    client, graph = make_client()

    first = await evaluate(client)
    second = await evaluate(client)

    assert first.correlation_id != second.correlation_id
    assert [call.client_request_id for call in graph.calls] == [
        first.correlation_id,
        second.correlation_id,
    ]
    assert [entry_of(body)["identifier"] for body in graph.bodies] == [
        first.correlation_id,
        second.correlation_id,
    ]
    assert all(call.client_request_id != "conversation-1" for call in graph.calls)
    assert {entry_of(body)["correlationId"] for body in graph.bodies} == {"conversation-1"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent", "location", "blueprint"),
    [
        (PurviewDlpAgentContext(AGENT_ID, TENANT_ID), AGENT_ID, None),
        (
            PurviewDlpAgentContext(AGENT_ID, TENANT_ID, blueprint_id=BLUEPRINT_ID),
            BLUEPRINT_ID,
            BLUEPRINT_ID,
        ),
        (
            PurviewDlpAgentContext(
                AGENT_ID, TENANT_ID, blueprint_id=BLUEPRINT_ID, application_id="app-id"
            ),
            "app-id",
            BLUEPRINT_ID,
        ),
        (PurviewDlpAgentContext(AGENT_ID, TENANT_ID, application_id="app-id"), "app-id", None),
        (PurviewDlpAgentContext(AGENT_ID, TENANT_ID, blueprint_id="  "), AGENT_ID, None),
    ],
)
async def test_scopes_the_application_location_to_the_blueprint_by_default(
    agent: PurviewDlpAgentContext, location: str, blueprint: str | None
) -> None:
    client, graph = make_client()

    await client.evaluate(
        "uploadText", "hello", agent, GraphTokens().resolve, session_id="conversation-1"
    )

    (body,) = graph.bodies
    application = body["contentToProcess"]["protectedAppMetadata"]["applicationLocation"]  # type: ignore[index]
    assert application["value"] == location
    (described,) = entry_of(body)["agents"]  # type: ignore[misc]
    assert described.get("blueprintId") == blueprint, "left out when unknown"
    assert ("blueprintId" in described) is (blueprint is not None)
    assert described["identifier"] == AGENT_ID


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [None, "", "   "])
async def test_names_an_agent_without_a_name_after_its_id(name: str | None) -> None:
    client, graph = make_client()
    agent = PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agent_name=name)

    await client.evaluate(
        "uploadText", "hello", agent, GraphTokens().resolve, session_id="conversation-1"
    )

    (body,) = graph.bodies
    assert entry_of(body)["name"] == f"{AGENT_ID} uploadText", "never empty"
    assert entry_of(body)["agents"][0]["name"] == AGENT_ID  # type: ignore[index]
    assert body["contentToProcess"]["integratedAppMetadata"]["name"] == AGENT_ID  # type: ignore[index]
    assert body["contentToProcess"]["protectedAppMetadata"]["name"] == AGENT_ID  # type: ignore[index]


@pytest.mark.asyncio
@pytest.mark.parametrize(("version", "sent"), [(None, "1.0"), (" ", "1.0"), ("2.3.1", "2.3.1")])
async def test_sends_the_agent_version(version: str | None, sent: str) -> None:
    client, graph = make_client()
    agent = PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agent_version=version)

    await client.evaluate(
        "uploadText", "hello", agent, GraphTokens().resolve, session_id="conversation-1"
    )

    request = graph.bodies[0]["contentToProcess"]
    assert entry_of(graph.bodies[0])["agents"][0]["version"] == sent  # type: ignore[index]
    assert request["integratedAppMetadata"]["version"] == sent  # type: ignore[index]
    assert request["protectedAppMetadata"]["version"] == sent  # type: ignore[index]


@pytest.mark.asyncio
async def test_numbers_calls_without_a_sequence_number_in_increasing_order() -> None:
    client, graph = make_client()

    for session_id in ("conversation-1", "conversation-2", "conversation-1"):
        await client.evaluate(
            "uploadText", "hello", AGENT, GraphTokens().resolve, session_id=session_id
        )

    entries = [entry_of(body) for body in graph.bodies]
    assert [entry["sequenceNumber"] for entry in entries] == [0, 1, 2]
    assert [entry["correlationId"] for entry in entries] == [
        "conversation-1",
        "conversation-2",
        "conversation-1",
    ]


@pytest.mark.asyncio
async def test_sends_every_string_as_valid_unicode() -> None:
    client, graph = make_client()
    agent = PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agent_name="Agent\ud800")

    result = await client.evaluate(
        "uploadText",
        "pair \ud83d\ude00 lone \udc00",
        agent,
        GraphTokens().resolve,
        session_id="s\udfff",
    )

    assert result is not None and result.evaluated is True
    (body,) = graph.bodies
    entry = entry_of(body)
    assert entry["content"]["data"] == "pair \U0001f600 lone \ufffd"  # type: ignore[index]
    assert entry["name"] == "Agent\ufffd uploadText"
    assert entry["correlationId"] == "s\ufffd"


@pytest.mark.asyncio
async def test_calls_the_user_the_token_names() -> None:
    client, graph = make_client()

    await evaluate(client, tokens=GraphTokens(user_id="user/with space"))

    (call,) = graph.calls
    assert call.url == (
        f"{GRAPH_BASE_URL}/users/user%2Fwith%20space/dataSecurityAndGovernance/processContent"
    )


@pytest.mark.asyncio
async def test_appends_the_path_to_a_graph_base_url_with_a_trailing_slash() -> None:
    client, graph = make_client(graph_base_url=f"{GRAPH_BASE_URL}/")

    await evaluate(client)

    assert graph.calls[0].url == ME_URL


# ---- decision --------------------------------------------------------------------------------


def actions_response(*actions: object, **members: object) -> GraphResponder:
    def respond(_body: JsonObject) -> FakeResponse:
        return json_response({"policyActions": list(actions), **members})

    return respond


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "restriction"),
    [
        ({"restrictionAction": "block"}, "block"),
        ({"restrictionAction": "Block"}, "Block"),
        ({"restrictionAction": "BLOCK"}, "BLOCK"),
        ({"action": "restrictAccess", "restrictionAction": "block"}, "block"),
        ({"action": "blockAccess"}, None),
        ({"action": "BLOCKACCESS", "restrictionAction": "warn"}, "warn"),
    ],
)
@pytest.mark.parametrize("activity", ["uploadText", "downloadText"])
async def test_blocks_on_a_block_restriction_or_block_access_in_any_case(
    action: JsonObject, restriction: str | None, activity: str
) -> None:
    client, _ = make_client(
        actions_response({"@odata.type": "#microsoft.graph.restrictAccessAction", **action})
    )

    result = await evaluate(client, activity=activity)

    assert result.allowed is False
    assert result.evaluated is True
    assert result.verified is True
    assert result.decision == PurviewDlpDecision(True, restriction, 1)
    assert result.block_reason == (
        "The request was blocked by a Microsoft Purview data loss prevention policy."
        if activity == "uploadText"
        else "The response was blocked by a Microsoft Purview data loss prevention policy."
    )


@pytest.mark.asyncio
async def test_allows_and_counts_actions_that_do_not_block() -> None:
    client, _ = make_client(
        actions_response(
            {"@odata.type": "#microsoft.graph.auditAction"},
            {"action": "restrictAccess", "restrictionAction": "warn"},
            {"action": "restrictAccess", "restrictionAction": "audit"},
            {"action": "notifyUser"},
        )
    )

    result = await evaluate(client)

    assert result.allowed is True
    assert result.verified is True
    assert result.block_reason is None
    assert result.decision == PurviewDlpDecision(False, "warn", 4), "the first restriction"


@pytest.mark.asyncio
async def test_reports_the_blocking_restriction_among_other_actions() -> None:
    client, _ = make_client(
        actions_response(
            {"restrictionAction": "warn"},
            {"action": "blockAccess"},
            {"restrictionAction": "block"},
        )
    )

    result = await evaluate(client)

    assert result.allowed is False
    assert result.decision == PurviewDlpDecision(True, "block", 3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malformed",
    [
        "block",
        None,
        5,
        {"restrictionAction": ["block"]},
        {"action": {"name": "blockAccess"}},
        {"restrictionAction": 1},
    ],
)
async def test_a_block_stands_beside_malformed_actions_and_processing_errors(
    malformed: object,
) -> None:
    client, _ = make_client(
        actions_response(malformed, {"restrictionAction": "Block"}, processingErrors=[{}]),
        fail_closed=False,
    )

    result = await evaluate(client)

    assert result.allowed is False
    assert result.evaluated is True
    assert result.decision == PurviewDlpDecision(True, "Block", 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", ["block", None, 5, {"restrictionAction": ["block"]}])
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_malformed_action_without_a_block_follows_the_fail_mode(
    malformed: object, fail_closed: bool
) -> None:
    client, _ = make_client(
        actions_response({"restrictionAction": "warn"}, malformed), fail_closed=fail_closed
    )

    result = await evaluate(client)

    assert result.evaluated is False
    assert result.allowed is not fail_closed
    assert result.error == "response had a policy action of another shape"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [202, 204])
async def test_an_accepted_response_without_a_body_is_an_evaluated_allow(status: int) -> None:
    client, _ = make_client(lambda _: FakeResponse(status, b""))

    result = await evaluate(client)

    assert result.allowed is True
    assert result.evaluated is True
    assert result.http_status == status
    assert result.decision == PurviewDlpDecision()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
@pytest.mark.parametrize("status", [301, 307, 400, 401, 403, 404, 429, 500, 503])
async def test_a_failed_request_follows_the_fail_mode_without_the_response_body(
    status: int, fail_closed: bool
) -> None:
    def respond(_body: JsonObject) -> FakeResponse:
        return json_response(
            {"error": {"code": "Forbidden", "message": "echoes the token eyJ.secret"}}, status
        )

    client, graph = make_client(respond, fail_closed=fail_closed)

    result = await evaluate(client)

    assert result.evaluated is False
    assert result.allowed is not fail_closed
    assert result.http_status == status
    assert result.error == f"http {status}"
    assert graph.calls[0].allow_redirects is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        (text_response("<html>busy</html>"), "non-JSON response"),
        (FakeResponse(200, b"\xff\xfe\x00"), "non-JSON response"),
        (FakeResponse(200, b""), "non-JSON response"),
        (json_response(None), "response was not a JSON object"),
        (json_response(["policyActions"]), "response was not a JSON object"),
        (json_response("allow"), "response was not a JSON object"),
        (json_response({}), "response had no list of policy actions"),
        (json_response({"policyActions": None}), "response had no list of policy actions"),
        (
            json_response({"policyActions": {"restrictionAction": "block"}}),
            "response had no list of policy actions",
        ),
        (json_response({"policyActions": "block"}), "response had no list of policy actions"),
        (
            json_response({"processingErrors": [{"errorCode": "badRequest"}]}),
            "processing errors: 1",
        ),
        (
            json_response({"policyActions": [], "processingErrors": [{}, {}]}),
            "processing errors: 2",
        ),
        (
            json_response({"policyActions": [], "processingErrors": {"code": "x"}}),
            "response had processingErrors that are not a list",
        ),
        (
            json_response({"policyActions": [], "processingErrors": "error"}),
            "response had processingErrors that are not a list",
        ),
    ],
)
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_response_without_a_decision_follows_the_fail_mode(
    response: FakeResponse, error: str, fail_closed: bool
) -> None:
    client, _ = make_client(lambda _: response, fail_closed=fail_closed)

    result = await evaluate(client)

    assert result.evaluated is False
    assert result.allowed is not fail_closed
    assert result.verified is False
    assert result.error == error
    assert result.http_status == 200
    assert result.block_reason == (
        "Data loss prevention validation is unavailable and this agent is configured to fail "
        "closed."
        if fail_closed
        else None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"policyActions": []},
        {"policyActions": [], "processingErrors": None},
        {"policyActions": [], "processingErrors": []},
        {"policyActions": [], "protectionScopeState": 5},
        {"policyActions": [{"action": "restrictAccess", "restrictionAction": None}]},
    ],
)
async def test_a_list_of_actions_without_a_block_or_errors_is_an_allow(
    payload: JsonObject,
) -> None:
    client, _ = make_client(lambda _: json_response(payload))

    result = await evaluate(client)

    assert result.allowed is True
    assert result.evaluated is True
    assert result.protection_scope_state is None


# ---- truncation ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sends_content_within_the_limit_whole() -> None:
    client, graph = make_client(max_content_characters=8)

    result = await evaluate(client, "abcdefgh")

    assert result.truncated is False
    assert entry_of(graph.bodies[0])["content"] == {
        "@odata.type": "microsoft.graph.textContent",
        "data": "abcdefgh",
    }
    assert entry_of(graph.bodies[0])["isTruncated"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_an_allow_of_truncated_content_follows_the_fail_mode(fail_closed: bool) -> None:
    client, graph = make_client(max_content_characters=4, fail_closed=fail_closed)

    result = await evaluate(client, "abcdefgh")

    entry = entry_of(graph.bodies[0])
    assert entry["content"]["data"] == "abcd"  # type: ignore[index]
    assert entry["isTruncated"] is True
    assert result.evaluated is True
    assert result.truncated is True
    assert result.verified is False
    assert result.allowed is not fail_closed
    assert result.error == TRUNCATED_ERROR
    assert result.block_reason == (
        "The content is too long to be fully validated by Microsoft Purview, and this agent is "
        "configured to fail closed."
        if fail_closed
        else None
    )


@pytest.mark.asyncio
async def test_a_block_of_truncated_content_blocks_even_when_failing_open() -> None:
    client, _ = make_client(block, max_content_characters=4)

    result = await evaluate(client, "4111 1111 1111 1111")

    assert result.allowed is False
    assert result.truncated is True
    assert result.verified is True
    assert result.error is None


@pytest.mark.asyncio
async def test_counts_characters_after_rejoining_split_surrogate_pairs() -> None:
    client, graph = make_client(max_content_characters=2)

    result = await evaluate(client, "\ud83d\ude00\ud83d\ude00")

    assert result.truncated is False
    assert entry_of(graph.bodies[0])["content"]["data"] == "\U0001f600\U0001f600"  # type: ignore[index]


@pytest.mark.asyncio
async def test_reads_only_a_prefix_of_very_long_content() -> None:
    client, graph = make_client(max_content_characters=10)
    text = "x" * 50_000_000

    started = time.perf_counter()
    result = await evaluate(client, text)
    elapsed = time.perf_counter() - started

    assert entry_of(graph.bodies[0])["content"]["data"] == "x" * 10  # type: ignore[index]
    assert result.truncated is True
    assert elapsed < 1.0


# ---- authentication --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [None, "", PurviewDlpToken(""), PurviewDlpToken("   "), "a raw token string", 5],
)
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_no_token_follows_the_fail_mode_without_a_call(
    token: object, fail_closed: bool
) -> None:
    client, graph = make_client(fail_closed=fail_closed)

    async def resolve(_agent: PurviewDlpAgentContext, _scopes: list[str]) -> object:
        return token

    result = await client.evaluate(
        "uploadText", "hello", AGENT, resolve, session_id="conversation-1"
    )  # type: ignore[arg-type]

    assert result is not None
    assert graph.calls == []
    assert result.evaluated is False
    assert result.allowed is not fail_closed
    assert result.error == "entra token unavailable"


@pytest.mark.asyncio
async def test_a_failing_token_resolver_reports_only_the_exception_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, graph = make_client()

    async def resolve(_agent: PurviewDlpAgentContext, _scopes: list[str]) -> PurviewDlpToken:
        raise RuntimeError("AADSTS error with password=hunter2 eyJ.secret")

    with caplog.at_level(logging.WARNING):
        result = await client.evaluate(
            "uploadText", "hello", AGENT, resolve, session_id="conversation-1"
        )

    assert result is not None
    assert graph.calls == []
    assert result.error == "entra token unavailable (RuntimeError)"
    assert "hunter2" not in repr(result)
    assert all("hunter2" not in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_an_empty_user_id_from_the_resolver_is_not_called() -> None:
    client, graph = make_client()

    result = await evaluate(client, tokens=GraphTokens(user_id=" "))

    assert graph.calls == []
    assert result.error == "entra token unavailable (ValueError)"


@pytest.mark.asyncio
async def test_runs_a_synchronous_token_resolver_off_the_event_loop() -> None:
    client, graph = make_client()
    loop_thread = threading.get_ident()
    threads: list[int] = []

    def resolve(_agent: PurviewDlpAgentContext, scopes: list[str]) -> PurviewDlpToken:
        threads.append(threading.get_ident())
        assert scopes == [GRAPH_SCOPE]
        return PurviewDlpToken("sync-token")

    result = await client.evaluate(
        "uploadText", "hello", AGENT, resolve, session_id="conversation-1"
    )

    assert result is not None and result.allowed is True
    assert threads and threads[0] != loop_thread
    assert graph.calls[0].authorization == "Bearer sync-token"


@pytest.mark.asyncio
async def test_a_blocking_synchronous_resolver_cannot_outlast_the_deadline() -> None:
    client, graph = make_client(timeout_seconds=0.2)
    release = threading.Event()

    def resolve(_agent: PurviewDlpAgentContext, _scopes: list[str]) -> PurviewDlpToken:
        release.wait(5)
        return PurviewDlpToken("late")

    started = time.perf_counter()
    try:
        result = await client.evaluate(
            "uploadText", "hello", AGENT, resolve, session_id="conversation-1"
        )
        elapsed = time.perf_counter() - started
    finally:
        release.set()

    assert result is not None
    assert result.error == "entra token unavailable (TimeoutError)"
    assert elapsed < 1.0
    assert graph.calls == []


@pytest.mark.asyncio
async def test_token_acquisition_and_the_request_share_one_deadline() -> None:
    async def slow_graph(_body: JsonObject) -> FakeResponse:
        await asyncio.sleep(5)
        return json_response(CLEAN)

    client, _ = make_client(slow_graph, timeout_seconds=0.3)

    async def slow_tokens(_agent: PurviewDlpAgentContext, _scopes: list[str]) -> PurviewDlpToken:
        await asyncio.sleep(0.2)
        return PurviewDlpToken("token")

    started = time.perf_counter()
    result = await client.evaluate(
        "uploadText", "hello", AGENT, slow_tokens, session_id="conversation-1"
    )
    elapsed = time.perf_counter() - started

    assert result is not None
    assert result.error == "request timeout"
    assert result.evaluated is False
    assert 0.25 < elapsed < 0.6


# ---- transport -------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raised", "error"),
    [
        (
            aiohttp.ClientConnectionError("connection reset; password=hunter2"),
            "request failed (ClientConnectionError)",
        ),
        (RuntimeError("circuit open"), "request failed (RuntimeError)"),
    ],
)
async def test_a_transport_failure_follows_the_fail_mode(raised: Exception, error: str) -> None:
    def respond(_body: JsonObject) -> FakeResponse:
        raise raised

    client, _ = make_client(respond, fail_closed=True)

    result = await evaluate(client)

    assert result.evaluated is False
    assert result.allowed is False
    assert result.error == error
    assert "hunter2" not in repr(result)


@pytest.mark.asyncio
async def test_an_unreadable_response_body_follows_the_fail_mode() -> None:
    class BrokenBody(FakeResponse):
        async def read(self) -> bytes:
            raise aiohttp.ClientPayloadError("truncated payload")

    client, _ = make_client(lambda _: BrokenBody(200, b""))

    result = await evaluate(client)

    assert result.evaluated is False
    assert result.http_status == 200
    assert result.error == "response body could not be read (ClientPayloadError)"


@pytest.mark.asyncio
async def test_the_callers_cancellation_is_not_a_result() -> None:
    entered = asyncio.Event()

    async def hanging(_body: JsonObject) -> FakeResponse:
        entered.set()
        await asyncio.sleep(5)
        return json_response(CLEAN)

    client, _ = make_client(hanging)
    call = asyncio.ensure_future(evaluate(client))
    await asyncio.wait_for(entered.wait(), timeout=1)

    call.cancel()

    with pytest.raises(asyncio.CancelledError):
        await call


@pytest.mark.asyncio
async def test_opens_and_closes_its_own_session_when_none_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions: list[FakeGraphSession] = []

    class OwnedSession(FakeGraphSession):
        closed = False

        async def __aenter__(self) -> OwnedSession:
            sessions.append(self)
            return self

        async def __aexit__(self, *_exc: object) -> None:
            self.closed = True

    monkeypatch.setattr(aiohttp, "ClientSession", OwnedSession)
    client = PurviewDlpClient(PurviewDlpOptions(enabled=True, graph_base_url=GRAPH_BASE_URL))

    result = await client.evaluate(
        "uploadText", "hello", AGENT, GraphTokens().resolve, session_id="conversation-1"
    )

    assert result is not None and result.allowed is True
    (session,) = sessions
    assert session.closed
    assert len(session.calls) == 1


# ---- what is not evaluated -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_does_nothing_when_disabled() -> None:
    graph = FakeGraphSession()
    tokens = GraphTokens()
    client = PurviewDlpClient(PurviewDlpOptions(), graph)  # type: ignore[arg-type]

    result = await client.evaluate(
        "uploadText", "4111 1111 1111 1111", AGENT, tokens.resolve, session_id="conversation-1"
    )

    assert result is None
    assert graph.calls == []
    assert tokens.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", " ", "\n\t "])
async def test_does_not_evaluate_empty_text(text: str) -> None:
    client, graph = make_client()
    tokens = GraphTokens()

    result = await client.evaluate(
        "uploadText", text, AGENT, tokens.resolve, session_id="conversation-1"
    )

    assert result is None
    assert graph.calls == []
    assert tokens.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({"activity": "uploadFile"}, ValueError),
        ({"text": ["hello"]}, TypeError),
        ({"agent": {"agent_id": AGENT_ID}}, TypeError),
        ({"agent": PurviewDlpAgentContext(" ", TENANT_ID)}, ValueError),
        ({"agent": PurviewDlpAgentContext(AGENT_ID, "")}, ValueError),
        ({"token_resolver": "token"}, TypeError),
        ({"sequence_number": -1}, ValueError),
        ({"sequence_number": True}, ValueError),
        ({"sequence_number": 2**63}, ValueError),
        ({"sequence_number": 1.0}, ValueError),
        ({"session_id": None}, ValueError),
        ({"session_id": ""}, ValueError),
        ({"session_id": "   "}, ValueError),
        ({"session_id": 7}, ValueError),
    ],
)
async def test_rejects_an_invalid_call(arguments: dict[str, object], error: type) -> None:
    client, graph = make_client()
    call: dict[str, object] = {
        "activity": "uploadText",
        "text": "hello",
        "agent": AGENT,
        "token_resolver": GraphTokens().resolve,
        "session_id": "conversation-1",
        **arguments,
    }

    with pytest.raises(error):
        await client.evaluate(**call)  # type: ignore[arg-type]

    assert graph.calls == []


@pytest.mark.asyncio
async def test_requires_the_session_id() -> None:
    client, graph = make_client()

    with pytest.raises(TypeError, match="session_id"):
        await client.evaluate("uploadText", "hello", AGENT, GraphTokens().resolve)  # type: ignore[call-arg]

    assert graph.calls == []


@pytest.mark.parametrize("fail_closed", [False, True])
def test_unavailable_follows_the_fail_mode(fail_closed: bool) -> None:
    client, _ = make_client(fail_closed=fail_closed)

    result = client.unavailable("downloadText", "no agent identity was resolved")

    assert result.evaluated is False
    assert result.allowed is not fail_closed
    assert result.activity == "downloadText"
    assert result.error == "no agent identity was resolved"
    assert str(uuid.UUID(result.correlation_id)) == result.correlation_id


def test_a_token_is_never_shown_in_its_repr() -> None:
    token = PurviewDlpToken("eyJ.secret.signature", AGENTIC_USER_ID)

    assert "secret" not in repr(token)
    assert AGENTIC_USER_ID in repr(token)
    assert dataclasses.replace(token).access_token == "eyJ.secret.signature"

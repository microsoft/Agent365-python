# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Runs the Purview interceptor under the real agent-hooks emitter (native core) against a fake
Microsoft Graph processContent API, alone and together with the Defender interceptor."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from agent_hooks import (
    AgentContext,
    AgentContextBuilder,
    CompositionConfig,
    Decision,
    EnforcementMode,
    InterceptionBlocked,
    InterceptionEmitter,
    SynthesisPolicy,
)
from microsoft_agents_a365.tooling.extensions.agenthooks import (
    A365DefenderCall,
    A365DefenderInterceptor,
    A365PurviewCall,
    A365PurviewCallResolver,
    A365PurviewInterceptor,
    add_a365_defender,
    add_a365_purview,
    create_protection_emitter,
)
from microsoft_agents_a365.tooling.protection.defender import (
    DefenderRtpAgentContext,
    DefenderRtpClient,
    DefenderRtpOptions,
)
from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpAgentContext,
    PurviewDlpClient,
    PurviewDlpDecision,
    PurviewDlpEvaluationResult,
    PurviewDlpOptions,
    PurviewDlpToken,
)

from ...protection.defender_fakes import (
    ENDPOINT,
    FakeDefenderSession,
    FakeResponse,
    JsonObject,
    TokenSource,
    json_response,
)
from ...protection.purview_fakes import (
    AGENT,
    AGENT_ID,
    CLEAN,
    GRAPH_BASE_URL,
    TENANT_ID,
    FakeGraphSession,
    GraphResponder,
    GraphTokens,
    activity_of,
    block,
    block_card_numbers,
    clean,
    entry_of,
    text_of,
)

CARD_PROMPT = "Please charge my credit card 4111 1111 1111 1111 exp 12/28 for the hotel booking"
CLEAN_PROMPT = "Find 2 flights from Seattle to San Francisco next week"
BLOCK_MESSAGE = "The request was blocked by a Microsoft Purview data loss prevention policy."
FAIL_CLOSED_MESSAGE = (
    "Data loss prevention validation is unavailable and this agent is configured to fail closed."
)
THREAT_URL = "https://malicious.example.test"


@dataclass
class Harness:
    """An emitter with the Purview interceptor registered, and what it sent."""

    emitter: InterceptionEmitter
    graph: FakeGraphSession
    interceptor: A365PurviewInterceptor
    evaluations: list[PurviewDlpEvaluationResult] = field(default_factory=list)

    async def settle(self) -> None:
        """Wait for the reply audits and the evaluation callbacks."""
        await self.interceptor.wait_for_pending_audits()
        # The evaluation callback runs on a worker thread; wait for every one before the test
        # reads what they recorded.
        await asyncio.get_running_loop().shutdown_default_executor()


@asynccontextmanager
async def harness(
    respond: GraphResponder = clean,
    *,
    fail_closed: bool = False,
    response_mode: str = "audit",
    timeout_seconds: float = 10.0,
    max_content_characters: int = 100000,
    resolve_call: A365PurviewCallResolver | None = None,
    emitter: InterceptionEmitter | None = None,
) -> AsyncIterator[Harness]:
    graph = FakeGraphSession(respond)
    options = PurviewDlpOptions(
        enabled=True,
        graph_base_url=GRAPH_BASE_URL,
        fail_closed=fail_closed,
        response_mode=response_mode,  # type: ignore[arg-type]
        timeout_seconds=timeout_seconds,
        max_content_characters=max_content_characters,
    )
    client = PurviewDlpClient(options, graph)  # type: ignore[arg-type]
    tokens = GraphTokens()
    evaluations: list[PurviewDlpEvaluationResult] = []
    interceptor = A365PurviewInterceptor(
        client,
        resolve_call or (lambda _context: A365PurviewCall(AGENT, tokens.resolve)),
        evaluations.append,
    )
    emitter = add_a365_purview(emitter or create_protection_emitter(purview=options), interceptor)
    h = Harness(emitter, graph, interceptor, evaluations)
    try:
        yield h
    finally:
        await h.settle()


def builder(session_id: str = "conversation:activity") -> AgentContextBuilder:
    return AgentContextBuilder(
        agent_id=AGENT_ID,
        framework="agent-framework",
        session_id=session_id,
        agent_name="SampleAgent",
    )


# ---- input -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_a_clean_message_and_sends_it_as_upload_text() -> None:
    b = builder()
    b.agent_startup(tools_registered=["Search"])

    async with harness(block_card_numbers) as h:
        record = await h.emitter.emit_unchecked(b.input(content=CLEAN_PROMPT))

    assert record.proceeds is True
    assert record.verdict.decision is Decision.ALLOW
    assert record.verdict.warnings == ()
    (call,) = h.graph.calls
    assert activity_of(call.body) == "uploadText"
    entry = entry_of(call.body)
    assert entry["content"]["data"] == CLEAN_PROMPT  # type: ignore[index]
    assert entry["correlationId"] == "conversation:activity"
    assert entry["sequenceNumber"] == 1, "the context's sequence"
    assert entry["name"] == "SampleAgent uploadText"
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is True and evaluation.allowed is True
    assert evaluation.correlation_id == call.client_request_id


@pytest.mark.asyncio
async def test_denies_a_message_a_dlp_policy_blocks() -> None:
    async with harness(block_card_numbers) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=CARD_PROMPT))

    assert record.proceeds is False
    assert record.verdict.decision is Decision.DENY
    assert record.verdict.reason == "purview:block"
    assert record.verdict.message == BLOCK_MESSAGE
    (evaluation,) = h.evaluations
    assert evaluation.decision == PurviewDlpDecision(True, "block", 1)
    assert record.verdict.evidence is not None
    assert record.verdict.evidence.artefact == "purview-verdict"
    assert record.verdict.evidence.verification_pointers == {
        "correlation": f"urn:a365:purview:{evaluation.correlation_id}"
    }


@pytest.mark.asyncio
async def test_emit_raises_interception_blocked_on_a_block() -> None:
    async with harness(block) as h:
        with pytest.raises(InterceptionBlocked) as blocked:
            await h.emitter.emit(builder().input(content=CARD_PROMPT))

    assert blocked.value.result.verdict.reason == "purview:block"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured", "expected"),
    [(None, "SampleAgent"), ("  ", "SampleAgent"), ("ConfiguredAgent", "ConfiguredAgent")],
)
async def test_names_the_agent_from_the_context_when_it_has_no_name(
    configured: str | None, expected: str
) -> None:
    agent = PurviewDlpAgentContext(AGENT_ID, TENANT_ID, agent_name=configured)

    async with harness(
        resolve_call=lambda _context: A365PurviewCall(agent, GraphTokens().resolve)
    ) as h:
        await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    entry = entry_of(h.graph.bodies[0])
    assert entry["name"] == f"{expected} uploadText"
    assert entry["agents"][0]["name"] == expected  # type: ignore[index]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "text"),
    [
        (
            [{"type": "text", "text": "card 4111 1111 1111 1111"}],
            "text\ncard 4111 1111 1111 1111",
        ),
        (
            {"number": 4111111111111111, "flag": True, "none": None, "parts": [1.5, "", "x"]},
            "4111111111111111\n1.5\nx",
        ),
        ({"nested": {"deeper": [["a"], {"b": "c"}]}}, "a\nc"),
    ],
)
async def test_sends_the_string_and_number_values_of_structured_content(
    content: object, text: str
) -> None:
    async with harness(block_card_numbers) as h:
        await h.emitter.emit_unchecked(builder().input(content=content))

    assert text_of(h.graph.bodies[0]) == text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "text"),
    [
        (("tuple", 7), "tuple\n7"),
        ([float("nan"), float("inf"), "finite"], "finite"),
    ],
)
async def test_reads_values_agent_hooks_would_not_pass_on(content: object, text: str) -> None:
    context = builder().input(content="placeholder")
    context["input"]["content"] = content

    async with harness() as h:
        await h.interceptor.intercept(context)

    assert text_of(h.graph.bodies[0]) == text


@pytest.mark.asyncio
async def test_reads_a_container_that_refers_to_itself_once() -> None:
    content: list[object] = ["first"]
    content.append(content)
    context = builder().input(content="placeholder")
    context["input"]["content"] = content

    async with harness() as h:
        verdict = await h.interceptor.intercept(context)

    assert verdict.decision is Decision.ALLOW
    assert text_of(h.graph.bodies[0]) == "first"


@pytest.mark.asyncio
async def test_blocks_a_card_number_in_structured_content() -> None:
    async with harness(block_card_numbers) as h:
        record = await h.emitter.emit_unchecked(
            builder().input(content=[{"type": "text", "text": CARD_PROMPT}])
        )

    assert record.proceeds is False
    assert record.verdict.reason == "purview:block"


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_structured_content_past_the_limit_is_sent_truncated(fail_closed: bool) -> None:
    content = [{"text": "a" * 6}, {"text": "b" * 6}, {"text": "card 4111 1111 1111 1111"}]

    async with harness(block_card_numbers, fail_closed=fail_closed, max_content_characters=10) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=content))

    entry = entry_of(h.graph.bodies[0])
    assert entry["content"]["data"] == "aaaaaa\nbbb"  # type: ignore[index]
    assert entry["isTruncated"] is True
    assert record.proceeds is not fail_closed, "an allow of truncated content follows the fail mode"


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
@pytest.mark.parametrize(
    "content",
    [[" " * 25, "card 4111 1111 1111 1111"], [" " * 30], [" " * 1_000_000 + "4111 1111"]],
)
async def test_blank_content_that_goes_on_past_the_limit_follows_the_fail_mode(
    fail_closed: bool, content: object
) -> None:
    async with harness(block, fail_closed=fail_closed, max_content_characters=10) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=content))

    assert h.graph.calls == [], "Purview was not called"
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is False
    assert evaluation.error == (
        "content exceeded max_content_characters (10) before any text; Purview was not called"
    )
    assert record.proceeds is not fail_closed
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"


@pytest.mark.asyncio
async def test_reads_only_what_the_limit_needs_of_a_long_structured_value() -> None:
    context = builder().input(content=["prefix", "x" * 50_000_000])

    async with harness(clean, max_content_characters=10) as h:
        started = time.perf_counter()
        verdict = await h.interceptor.intercept(context)
        elapsed = time.perf_counter() - started

    entry = entry_of(h.graph.bodies[0])
    assert entry["content"]["data"] == "prefix\nxxx"  # type: ignore[index]
    assert entry["isTruncated"] is True
    assert verdict.decision is Decision.ALLOW, "fail open"
    (warning,) = verdict.warnings
    assert warning.reason == "purview:unverified", "an allow of truncated content is unverified"
    assert elapsed < 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize("session", [None, {}, {"id": ""}, {"id": "   "}, {"id": 7}])
async def test_a_context_without_a_session_id_follows_the_fail_mode(session: object) -> None:
    context = builder().input(content=CLEAN_PROMPT)
    if session is None:
        del context["session"]
    else:
        context["session"] = session

    async with harness(clean, fail_closed=True) as h:
        verdict = await h.interceptor.intercept(context)

    assert verdict.decision is Decision.DENY
    assert verdict.reason == "runtime_error:purview_unverified"
    assert h.graph.calls == []
    (evaluation,) = h.evaluations
    assert evaluation.error == "evaluation failed (ValueError)"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [[" ", "\n"], {"flag": True, "none": None}, [], {}, [[], {}]])
async def test_allows_content_without_text_without_a_call(content: object) -> None:
    async with harness(block, fail_closed=True, max_content_characters=10) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=content))

    assert record.proceeds is True
    assert h.graph.calls == []
    assert h.evaluations == []


@pytest.mark.asyncio
async def test_content_that_cannot_be_read_follows_the_fail_mode() -> None:
    context = builder().input(content="placeholder")
    context["input"]["content"] = [10**5000]

    async with harness(block, fail_closed=True) as h:
        verdict = await h.interceptor.intercept(context)

    assert verdict.decision is Decision.DENY
    assert verdict.reason == "runtime_error:purview_unverified"
    (evaluation,) = h.evaluations
    assert evaluation.error == "content could not be read (ValueError)"
    assert h.graph.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   ", None])
async def test_allows_empty_content_without_resolving_a_call(content: object) -> None:
    resolved: list[AgentContext] = []

    def resolve_call(context: AgentContext) -> A365PurviewCall | None:
        resolved.append(context)
        return None

    async with harness(block, resolve_call=resolve_call, fail_closed=True) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=content))

    assert record.proceeds is True
    assert resolved == []
    assert h.graph.calls == []
    assert h.evaluations == []


# ---- output ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audits_the_reply_in_the_background_and_allows_it_at_once() -> None:
    release = asyncio.Event()

    async def slow_block(body: JsonObject) -> FakeResponse:
        await release.wait()
        return block(body)

    async with harness(slow_block) as h:
        started = time.perf_counter()
        record = await h.emitter.emit_unchecked(builder().output(content="Your card ends in 1111."))
        elapsed = time.perf_counter() - started
        assert h.evaluations == [], "not awaited"
        release.set()

    assert record.proceeds is True
    assert record.verdict.warnings == ()
    assert elapsed < 0.5
    (call,) = h.graph.calls
    assert activity_of(call.body) == "downloadText"
    assert entry_of(call.body)["name"] == "SampleAgent downloadText"
    (evaluation,) = h.evaluations
    assert evaluation.activity == "downloadText"
    assert evaluation.evaluated is True
    assert evaluation.correlation_id == call.client_request_id


@pytest.mark.asyncio
async def test_a_reply_audit_outlives_the_emitters_timeout() -> None:
    async def slow_clean(body: JsonObject) -> FakeResponse:
        await asyncio.sleep(0.5)
        return clean(body)

    # A host's own emitter whose timeout is far below the Purview call's.
    emitter = InterceptionEmitter(
        mode=EnforcementMode.ENFORCE,
        timeout=0.1,
        composition=CompositionConfig.strictest(SynthesisPolicy.DENY),
    )

    async with harness(slow_clean, emitter=emitter) as h:
        record = await h.emitter.emit_unchecked(builder().output(content="Here you go."))

    assert record.proceeds is True
    assert record.verdict.reason is None, "not an interceptor timeout"
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is True and evaluation.allowed is True


@pytest.mark.asyncio
async def test_a_reply_audit_is_bounded_by_the_client_timeout() -> None:
    async def hanging(_body: JsonObject) -> FakeResponse:
        await asyncio.sleep(30)
        return json_response(CLEAN)

    async with harness(hanging, timeout_seconds=0.2, fail_closed=True) as h:
        record = await h.emitter.emit_unchecked(builder().output(content="Here you go."))
        started = time.perf_counter()
        await h.interceptor.wait_for_pending_audits()
        elapsed = time.perf_counter() - started

    assert record.proceeds is True, "an audit never blocks the reply"
    assert elapsed < 1.0
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is False
    assert evaluation.error == "request timeout"
    assert evaluation.correlation_id == h.graph.calls[0].client_request_id


@pytest.mark.asyncio
@pytest.mark.parametrize("is_async", [False, True])
async def test_a_reply_audit_contains_a_failing_call_resolver(
    is_async: bool, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(_context: AgentContext) -> A365PurviewCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    async def failing_async(_context: AgentContext) -> A365PurviewCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    with caplog.at_level(logging.WARNING):
        async with harness(
            resolve_call=failing_async if is_async else failing, fail_closed=True
        ) as h:
            record = await h.emitter.emit_unchecked(builder().output(content="Here you go."))

    assert record.proceeds is True
    assert record.verdict.warnings == ()
    assert h.graph.calls == []
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is False
    assert evaluation.error == "evaluation failed (RuntimeError)"
    assert not any("never retrieved" in entry.getMessage() for entry in caplog.records)


@pytest.mark.asyncio
async def test_keeps_a_strong_reference_to_each_reply_audit() -> None:
    release = asyncio.Event()

    async def slow_clean(body: JsonObject) -> FakeResponse:
        await release.wait()
        return clean(body)

    async with harness(slow_clean) as h:
        await h.emitter.emit_unchecked(builder().output(content="first"))
        await h.emitter.emit_unchecked(builder().output(content="second"))
        assert len(h.interceptor._audits) == 2
        release.set()
        await h.interceptor.wait_for_pending_audits()
        assert h.interceptor._audits == set()

    assert len(h.evaluations) == 2


@pytest.mark.asyncio
async def test_enforces_the_reply_in_the_enforce_response_mode() -> None:
    async with harness(block, response_mode="enforce") as h:
        record = await h.emitter.emit_unchecked(
            builder().output(content="Card 4111 1111 1111 1111")
        )

    assert record.proceeds is False
    assert record.verdict.reason == "purview:block"
    assert record.verdict.message == (
        "The response was blocked by a Microsoft Purview data loss prevention policy."
    )
    assert activity_of(h.graph.bodies[0]) == "downloadText"
    (evaluation,) = h.evaluations
    assert record.verdict.evidence is not None
    assert record.verdict.evidence.verification_pointers == {
        "correlation": f"urn:a365:purview:{evaluation.correlation_id}"
    }


@pytest.mark.asyncio
async def test_allows_a_clean_reply_in_the_enforce_response_mode() -> None:
    async with harness(response_mode="enforce") as h:
        record = await h.emitter.emit_unchecked(builder().output(content="Here you go."))

    assert record.proceeds is True
    assert record.verdict.warnings == ()
    (evaluation,) = h.evaluations
    assert evaluation.activity == "downloadText" and evaluation.evaluated is True


# ---- what Purview does not evaluate ----------------------------------------------------------


@pytest.mark.asyncio
async def test_does_not_resolve_a_call_for_points_purview_does_not_evaluate() -> None:
    resolved: list[str] = []

    def resolve_call(context: AgentContext) -> A365PurviewCall | None:
        resolved.append(context["interception_point"])
        raise AssertionError("not expected")

    b = builder()
    async with harness(block, resolve_call=resolve_call, fail_closed=True) as h:
        for context in (
            b.agent_startup(tools_registered=["Search"]),
            b.pre_model_call(model_id="gpt-4o", messages=[{"role": "user", "content": "hi"}]),
            b.post_model_call(model_id="gpt-4o", content="hi", tool_calls=[], finish_reason="stop"),
            b.pre_tool_call(call_id="call-1", name="Pay", args={"card": "4111 1111 1111 1111"}),
            b.post_tool_call(call_id="call-1", name="Pay", args={}, value="paid"),
            b.agent_shutdown(reason="completed"),
        ):
            record = await h.emitter.emit_unchecked(context)
            assert record.proceeds is True

    assert resolved == []
    assert h.graph.calls == []


@pytest.mark.asyncio
async def test_does_nothing_when_disabled() -> None:
    def resolve_call(_context: AgentContext) -> A365PurviewCall | None:
        raise AssertionError("not expected")

    graph = FakeGraphSession(block)
    options = PurviewDlpOptions()
    interceptor = A365PurviewInterceptor(
        PurviewDlpClient(options, graph),  # type: ignore[arg-type]
        resolve_call,
    )
    emitter = add_a365_purview(create_protection_emitter(purview=options), interceptor)

    for context in (builder().input(content=CARD_PROMPT), builder().output(content=CARD_PROMPT)):
        record = await emitter.emit_unchecked(context)
        assert record.proceeds is True
        assert record.verdict.warnings == ()

    await interceptor.wait_for_pending_audits()
    assert graph.calls == []


# ---- fail mode -------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_follows_the_fail_mode_when_no_identity_is_resolved(fail_closed: bool) -> None:
    async with harness(block, fail_closed=fail_closed, resolve_call=lambda _context: None) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    assert h.graph.calls == []
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is False
    assert evaluation.error == "no agent identity was resolved"
    assert record.proceeds is not fail_closed
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"
    assert warning.message == "no agent identity was resolved"
    if fail_closed:
        assert record.verdict.reason == "runtime_error:purview_unverified"
        assert record.verdict.message == FAIL_CLOSED_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_failing_call_resolver_follows_the_fail_mode(
    is_async: bool, fail_closed: bool, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(_context: AgentContext) -> A365PurviewCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    async def failing_async(_context: AgentContext) -> A365PurviewCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    with caplog.at_level(logging.WARNING):
        async with harness(
            resolve_call=failing_async if is_async else failing, fail_closed=fail_closed
        ) as h:
            record = await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    assert h.graph.calls == []
    assert not (record.verdict.reason or "").startswith("host_error:")
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"
    assert warning.message == "evaluation failed (RuntimeError)", "only the type reaches the record"
    assert "hunter2" not in repr(record)
    assert any("hunter2" in (entry.exc_text or "") for entry in caplog.records), "it is logged"
    assert record.proceeds is not fail_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_failing_token_resolver_follows_the_fail_mode(fail_closed: bool) -> None:
    async def failing_tokens(_agent: PurviewDlpAgentContext, _scopes: list[str]) -> PurviewDlpToken:
        raise RuntimeError("AADSTS65001")

    async with harness(
        fail_closed=fail_closed,
        resolve_call=lambda _context: A365PurviewCall(AGENT, failing_tokens),
    ) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    assert h.graph.calls == []
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"
    assert warning.message == "entra token unavailable (RuntimeError)"
    assert record.proceeds is not fail_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("respond", "error"),
    [
        (lambda _body: json_response({"error": {"code": "Forbidden"}}, 403), "http 403"),
        (
            lambda _body: json_response({"policyActions": [], "processingErrors": [{}]}),
            "processing errors: 1",
        ),
    ],
)
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_no_decision_follows_the_fail_mode(
    respond: GraphResponder, error: str, fail_closed: bool
) -> None:
    async with harness(respond, fail_closed=fail_closed) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    assert record.proceeds is not fail_closed
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"
    assert warning.message == error
    if fail_closed:
        assert record.verdict.reason == "runtime_error:purview_unverified"
        assert record.verdict.message == FAIL_CLOSED_MESSAGE


@pytest.mark.asyncio
async def test_a_purview_timeout_fails_open_before_the_emitter_times_out() -> None:
    async def hanging(_body: JsonObject) -> FakeResponse:
        await asyncio.sleep(30)
        return json_response(CLEAN)

    async with harness(hanging, timeout_seconds=0.2) as h:
        record = await h.emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))

    assert record.proceeds is True, "fail open, not host_error:interceptor_timeout"
    (warning,) = record.verdict.warnings
    assert warning.message == "request timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_an_allow_of_truncated_content_follows_the_fail_mode(fail_closed: bool) -> None:
    async with harness(block_card_numbers, fail_closed=fail_closed, max_content_characters=10) as h:
        record = await h.emitter.emit_unchecked(
            builder().input(content="a" * 10 + " card 4111 1111 1111 1111")
        )

    assert text_of(h.graph.bodies[0]) == "a" * 10
    assert entry_of(h.graph.bodies[0])["isTruncated"] is True
    assert record.proceeds is not fail_closed
    (warning,) = record.verdict.warnings
    assert warning.reason == "purview:unverified"
    assert warning.message == (
        "content exceeded max_content_characters; Purview evaluated a truncated copy"
    )
    if fail_closed:
        assert record.verdict.message == (
            "The content is too long to be fully validated by Microsoft Purview, and this agent "
            "is configured to fail closed."
        )


@pytest.mark.asyncio
async def test_a_block_of_truncated_content_blocks_even_when_failing_open() -> None:
    async with harness(block_card_numbers, max_content_characters=10) as h:
        record = await h.emitter.emit_unchecked(
            builder().input(content="4111 1111 1111 1111 and a long tail")
        )

    assert record.proceeds is False
    assert record.verdict.reason == "purview:block"


# ---- callbacks -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failing_evaluation_callback_does_not_change_the_verdict() -> None:
    def failing_callback(_result: PurviewDlpEvaluationResult) -> None:
        raise RuntimeError("telemetry is down")

    graph = FakeGraphSession(block)
    options = PurviewDlpOptions(enabled=True, graph_base_url=GRAPH_BASE_URL)
    emitter = add_a365_purview(
        create_protection_emitter(purview=options),
        A365PurviewInterceptor(
            PurviewDlpClient(options, graph),  # type: ignore[arg-type]
            lambda _context: A365PurviewCall(AGENT, GraphTokens().resolve),
            failing_callback,
        ),
    )

    try:
        record = await emitter.emit_unchecked(builder().input(content=CARD_PROMPT))
    finally:
        await asyncio.get_running_loop().shutdown_default_executor()

    assert record.proceeds is False
    assert record.verdict.reason == "purview:block"


@pytest.mark.asyncio
async def test_a_slow_evaluation_callback_does_not_hold_up_or_change_the_verdict() -> None:
    release = threading.Event()
    seen: list[PurviewDlpEvaluationResult] = []

    def slow_callback(result: PurviewDlpEvaluationResult) -> None:
        release.wait(5)
        seen.append(result)

    options = PurviewDlpOptions(enabled=True, graph_base_url=GRAPH_BASE_URL, timeout_seconds=0.25)
    emitter = add_a365_purview(
        create_protection_emitter(
            interceptor_timeout_seconds=0.5,
            defender=DefenderRtpOptions(timeout_seconds=0.25),
            purview=options,
        ),
        A365PurviewInterceptor(
            PurviewDlpClient(options, FakeGraphSession(clean)),  # type: ignore[arg-type]
            lambda _context: A365PurviewCall(AGENT, GraphTokens().resolve),
            slow_callback,
        ),
    )

    started = time.perf_counter()
    try:
        record = await emitter.emit_unchecked(builder().input(content=CLEAN_PROMPT))
        elapsed = time.perf_counter() - started
    finally:
        release.set()
        await asyncio.get_running_loop().shutdown_default_executor()

    assert record.proceeds is True
    assert record.verdict.reason is None, "not an interceptor timeout"
    assert elapsed < 0.5
    (evaluation,) = seen
    assert evaluation.evaluated is True and evaluation.allowed is True


# ---- mapping ---------------------------------------------------------------------------------


def test_maps_a_block_to_a_deny_with_evidence() -> None:
    verdict = A365PurviewInterceptor.to_verdict(
        PurviewDlpEvaluationResult(
            allowed=False,
            evaluated=True,
            activity="uploadText",
            correlation_id="cid 1",
            decision=PurviewDlpDecision(True, "block", 1),
        )
    )

    assert verdict.decision is Decision.DENY
    assert verdict.reason == "purview:block"
    assert verdict.message == BLOCK_MESSAGE
    assert verdict.evidence is not None
    assert verdict.evidence.verification_pointers == {"correlation": "urn:a365:purview:cid%201"}


def test_maps_an_evaluated_allow_to_a_plain_allow() -> None:
    verdict = A365PurviewInterceptor.to_verdict(
        PurviewDlpEvaluationResult(
            allowed=True, evaluated=True, decision=PurviewDlpDecision(False, None, 2)
        )
    )

    assert verdict.decision is Decision.ALLOW
    assert verdict.warnings == ()


# ---- emitter ---------------------------------------------------------------------------------


def test_the_emitter_timeout_counts_purview_only_when_it_is_enabled() -> None:
    defender = DefenderRtpOptions(timeout_seconds=3)

    def purview(timeout: float, enabled: bool = True) -> PurviewDlpOptions:
        return PurviewDlpOptions(enabled=enabled, timeout_seconds=timeout)

    assert create_protection_emitter(defender=defender, purview=purview(7))._timeout == 9.0
    assert create_protection_emitter(defender=defender, purview=purview(1))._timeout == 5.0
    assert create_protection_emitter(purview=purview(20))._timeout == 22.0
    assert create_protection_emitter(purview=purview(7))._timeout == 12.0, "the Defender default"
    assert create_protection_emitter(defender=defender, purview=purview(20, False))._timeout == 5.0
    assert create_protection_emitter(purview=purview(20, False))._timeout == 12.0
    assert create_protection_emitter(defender=defender)._timeout == 5.0
    assert create_protection_emitter()._timeout == 12.0


@pytest.mark.parametrize("timeout", [float("nan"), float("inf")])
def test_rejects_an_enabled_purview_timeout_that_leaves_no_interceptor_timeout(
    timeout: float,
) -> None:
    with pytest.raises(ValueError, match="interceptor_timeout_seconds"):
        create_protection_emitter(purview=PurviewDlpOptions(enabled=True, timeout_seconds=timeout))

    disabled = PurviewDlpOptions(enabled=False, timeout_seconds=timeout)
    assert create_protection_emitter(purview=disabled)._timeout == 12.0


@pytest.mark.parametrize(
    ("timeout", "purview_timeout", "client"),
    [(5.0, 7.0, "Purview"), (7.0, 7.0, "Purview"), (2.0, 1.0, "Defender")],
)
def test_rejects_an_interceptor_timeout_that_does_not_exceed_the_client_timeouts(
    timeout: float, purview_timeout: float, client: str
) -> None:
    with pytest.raises(ValueError, match=f"must exceed the {client} timeout"):
        create_protection_emitter(
            interceptor_timeout_seconds=timeout,
            defender=DefenderRtpOptions(timeout_seconds=3),
            purview=PurviewDlpOptions(enabled=True, timeout_seconds=purview_timeout),
        )


def test_an_interceptor_timeout_need_not_exceed_a_disabled_purview_timeout() -> None:
    emitter = create_protection_emitter(
        interceptor_timeout_seconds=5,
        defender=DefenderRtpOptions(timeout_seconds=3),
        purview=PurviewDlpOptions(enabled=False, timeout_seconds=7),
    )

    assert emitter._timeout == 5


def test_registers_the_interceptor_under_the_purview_name() -> None:
    interceptor = A365PurviewInterceptor(
        PurviewDlpClient(PurviewDlpOptions()), lambda _context: None
    )

    emitter = add_a365_purview(create_protection_emitter(), interceptor)

    assert emitter._interceptors == [interceptor]
    assert emitter._names == ["purview"]
    assert A365PurviewInterceptor.NAME == "purview"


def test_requires_a_client_and_a_call_resolver() -> None:
    client = PurviewDlpClient(PurviewDlpOptions())

    with pytest.raises(TypeError, match="client"):
        A365PurviewInterceptor(None, lambda _context: None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="resolve_call"):
        A365PurviewInterceptor(client, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="interceptor"):
        add_a365_purview(create_protection_emitter(), None)  # type: ignore[arg-type]


# ---- Defender and Purview on one emitter -----------------------------------------------------


def defender_blocks_threat_urls(body: JsonObject) -> FakeResponse:
    if THREAT_URL in str(body["target"]):
        return json_response({"decision": "deny", "reason": "prevention_blocked"})
    return json_response({"decision": "allow"})


@asynccontextmanager
async def both() -> AsyncIterator[tuple[InterceptionEmitter, FakeDefenderSession, Harness]]:
    defender_options = DefenderRtpOptions(enabled=True, endpoint=ENDPOINT, timeout_seconds=5)
    purview_options = PurviewDlpOptions(enabled=True, graph_base_url=GRAPH_BASE_URL)
    defender_endpoint = FakeDefenderSession(defender_blocks_threat_urls)
    emitter = add_a365_defender(
        create_protection_emitter(defender=defender_options, purview=purview_options),
        A365DefenderInterceptor(
            DefenderRtpClient(defender_options, defender_endpoint),  # type: ignore[arg-type]
            lambda _context: A365DefenderCall(
                DefenderRtpAgentContext(agent_id=AGENT_ID, tenant_id=TENANT_ID),
                TokenSource().resolve,
            ),
        ),
    )
    async with harness(block_card_numbers, emitter=emitter) as h:
        yield emitter, defender_endpoint, h


@pytest.mark.asyncio
async def test_defender_and_purview_both_allow_a_clean_turn() -> None:
    b = builder()

    async with both() as (emitter, defender, h):
        records = [
            await emitter.emit_unchecked(b.input(content=CLEAN_PROMPT)),
            await emitter.emit_unchecked(
                b.pre_tool_call(call_id="call-1", name="Search", args={"query": "flights"})
            ),
            await emitter.emit_unchecked(
                b.post_tool_call(call_id="call-1", name="Search", args={}, value="2 flights")
            ),
            await emitter.emit_unchecked(b.output(content="Here are two flights.")),
        ]

    assert all(record.proceeds for record in records)
    assert emitter._timeout == 12.0
    assert [body["interception_point"] for body in defender.bodies] == [
        "input",
        "pre_tool_call",
        "post_tool_call",
        "output",
    ]
    assert [activity_of(body) for body in h.graph.bodies] == ["uploadText", "downloadText"]


@pytest.mark.asyncio
async def test_purview_denies_a_message_defender_allows() -> None:
    async with both() as (emitter, defender, h):
        record = await emitter.emit_unchecked(builder().input(content=CARD_PROMPT))

    assert record.proceeds is False
    assert record.verdict.reason == "purview:block"
    assert len(defender.bodies) == 1, "both run under parallel/strictest"
    assert len(h.graph.bodies) == 1


@pytest.mark.asyncio
async def test_defender_denies_a_tool_call_purview_does_not_evaluate() -> None:
    async with both() as (emitter, _defender, h):
        record = await emitter.emit_unchecked(
            builder().pre_tool_call(call_id="call-1", name="FetchPage", args={"url": THREAT_URL})
        )

    assert record.proceeds is False
    assert record.verdict.reason == "defender:block:prevention_blocked"
    assert h.graph.bodies == []

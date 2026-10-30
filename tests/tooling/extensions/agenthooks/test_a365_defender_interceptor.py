# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Runs the Defender interceptor under the real agent-hooks emitter (native core) against a
fake prevention endpoint."""

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
    A365DefenderCallResolver,
    A365DefenderInterceptor,
    add_a365_defender,
    create_protection_emitter,
)
from microsoft_agents_a365.tooling.protection.defender import (
    DefenderRtpAgentContext,
    DefenderRtpClient,
    DefenderRtpEvaluationResult,
    DefenderRtpOptions,
    DefenderRtpVerdict,
    DefenderRtpWarning,
)

from ...protection.defender_fakes import (
    AGENT_ID,
    ENDPOINT,
    TENANT_ID,
    FakeDefenderSession,
    FakeResponse,
    JsonObject,
    Responder,
    TokenSource,
    json_response,
)

THREAT_URL = "https://malicious.example.test"


@dataclass
class Harness:
    """An emitter with the Defender interceptor registered, and what it sent."""

    emitter: InterceptionEmitter
    endpoint: FakeDefenderSession
    client: DefenderRtpClient
    evaluations: list[DefenderRtpEvaluationResult] = field(default_factory=list)


@asynccontextmanager
async def harness(
    respond: Responder,
    *,
    fail_closed: bool = False,
    agent_id: str = AGENT_ID,
    resolve_nothing: bool = False,
    timeout_seconds: float = 10.0,
) -> AsyncIterator[Harness]:
    endpoint = FakeDefenderSession(respond)
    options = DefenderRtpOptions(
        enabled=True,
        endpoint=ENDPOINT,
        fail_closed=fail_closed,
        timeout_seconds=timeout_seconds,
    )
    client = DefenderRtpClient(options, endpoint)  # type: ignore[arg-type]
    tokens = TokenSource()
    agent = DefenderRtpAgentContext(
        agent_id=agent_id, tenant_id=TENANT_ID, user_id="user-object-id"
    )
    evaluations: list[DefenderRtpEvaluationResult] = []
    emitter = add_a365_defender(
        create_protection_emitter(defender=options),
        A365DefenderInterceptor(
            client,
            lambda _context: None if resolve_nothing else A365DefenderCall(agent, tokens.resolve),
            evaluations.append,
        ),
    )
    try:
        yield Harness(emitter, endpoint, client, evaluations)
    finally:
        # The evaluation callback runs on a worker thread; wait for every one before the test
        # reads what they recorded.
        await asyncio.get_running_loop().shutdown_default_executor()


def allow(_body: JsonObject) -> FakeResponse:
    return json_response({"decision": "allow"})


@pytest.mark.asyncio
async def test_forwards_the_emitted_context_and_allows() -> None:
    builder = AgentContextBuilder(
        agent_id=AGENT_ID,
        framework="agent-framework",
        session_id="conversation:activity",
        agent_name="SampleAgent",
    )

    async with harness(allow) as h:
        record = await h.emitter.emit_unchecked(
            builder.input(content="Find the latest release notes")
        )

    assert record.proceeds is True
    assert record.verdict.decision is Decision.ALLOW
    (body,) = h.endpoint.bodies
    assert body["spec"] == "agent-hooks/0.1"
    assert body["interception_point"] == "input"
    assert body["agent"]["id"] == AGENT_ID
    assert body["agent"]["framework"] == "agent-framework"
    assert body["session"]["id"] == "conversation:activity"
    assert body["sequence"] == 0
    assert body["tenant"] == {"id": TENANT_ID}
    assert body["actor"] == {"id": "user-object-id", "kind": "human"}
    assert body["target"] == body["input"]
    (evaluation,) = h.evaluations
    assert evaluation.correlation_id == h.endpoint.calls[0].correlation_id


@pytest.mark.asyncio
async def test_blocks_a_tool_call_defender_denies() -> None:
    def respond(body: JsonObject) -> FakeResponse:
        if body["interception_point"] == "pre_tool_call":
            return json_response({
                "decision": "deny",
                "reason": "prevention_blocked",
                "message": "Known malicious URL.",
                "result_labels": ["MaliciousUrl"],
            })
        return json_response({"decision": "allow"})

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-1")

    async with harness(respond) as h:
        record = await h.emitter.emit_unchecked(
            builder.pre_tool_call(call_id="call-1", name="FetchPage", args={"url": THREAT_URL})
        )

    assert record.proceeds is False
    assert record.verdict.decision is Decision.DENY
    assert record.verdict.reason == "defender:block:prevention_blocked"
    assert record.verdict.message == "Known malicious URL."
    assert record.decided_by == 0
    (body,) = h.endpoint.bodies
    assert body["tool_call"] == {
        "id": "call-1",
        "name": "FetchPage",
        "args": {"url": THREAT_URL},
    }
    assert body["target"] == body["tool_call"]["args"]


@pytest.mark.asyncio
async def test_emit_raises_interception_blocked_on_a_deny() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-1")

    async with harness(lambda _: json_response({"decision": "deny"})) as h:
        with pytest.raises(InterceptionBlocked) as blocked:
            await h.emitter.emit(builder.output(content="Here are three results."))

    assert blocked.value.result.verdict.reason == "defender:block"
    assert blocked.value.result.verdict.message == "Blocked by Microsoft Defender for AI."


@pytest.mark.asyncio
async def test_keeps_defender_warnings_and_labels_on_an_allow() -> None:
    def annotate(_body: JsonObject) -> FakeResponse:
        return json_response({
            "decision": "allow",
            "warnings": [{"reason": "prevention_annotated", "message": "Suspicious URL."}],
            "result_labels": ["MaliciousContentPropagation"],
        })

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-1")

    async with harness(annotate) as h:
        record = await h.emitter.emit_unchecked(
            builder.pre_tool_call(call_id="call-1", name="FetchPage", args={"url": THREAT_URL})
        )

    assert record.proceeds is True
    assert [(w.reason, w.message) for w in record.verdict.warnings] == [
        ("prevention_annotated", "Suspicious URL.")
    ]
    assert record.verdict.result_labels == ("MaliciousContentPropagation",)


def test_maps_a_defender_deny_to_an_agent_hooks_verdict_with_evidence_and_labels() -> None:
    verdict = A365DefenderInterceptor.to_verdict(
        DefenderRtpEvaluationResult(
            allowed=False,
            evaluated=True,
            interception_point="input",
            correlation_id="cid-1",
            block_reason="Prompt injection detected.",
            verdict=DefenderRtpVerdict(
                decision="deny", reason="prevention_blocked", result_labels=("PromptInjection",)
            ),
        )
    )

    assert verdict.decision is Decision.DENY
    assert verdict.reason == "defender:block:prevention_blocked"
    assert verdict.message == "Prompt injection detected."
    assert verdict.result_labels == ("PromptInjection",)
    assert verdict.evidence is not None
    assert verdict.evidence.artefact == "defender-verdict"
    assert verdict.evidence.verification_pointers == {"correlation": "urn:a365:defender:cid-1"}


def test_maps_a_defender_reason_to_a_safe_verdict_reason() -> None:
    verdict = A365DefenderInterceptor.to_verdict(
        DefenderRtpEvaluationResult(
            allowed=False,
            evaluated=True,
            verdict=DefenderRtpVerdict(decision="deny", reason="blocked by policy/42"),
        )
    )

    assert verdict.reason == "defender:block:blocked_by_policy_42"


def test_maps_defender_warnings_without_a_reason() -> None:
    verdict = A365DefenderInterceptor.to_verdict(
        DefenderRtpEvaluationResult(
            allowed=True,
            evaluated=True,
            verdict=DefenderRtpVerdict(warnings=(DefenderRtpWarning(None, None),)),
        )
    )

    assert verdict.decision is Decision.ALLOW
    assert [(w.reason, w.message) for w in verdict.warnings] == [("defender:warning", "")]


@pytest.mark.asyncio
async def test_allows_with_a_warning_when_fail_open_defender_is_unavailable() -> None:
    def forbidden(_body: JsonObject) -> FakeResponse:
        return json_response(
            {
                "title": "Forbidden",
                "detail": "The calling application is not allowed to use the third-party "
                "prevention endpoint.",
            },
            status=403,
        )

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-2")

    async with harness(forbidden) as h:
        record = await h.emitter.emit_unchecked(builder.output(content="Here are three results."))

    assert record.proceeds is True
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message is not None
    assert "not allowed to use the third-party prevention endpoint" in warning.message


@pytest.mark.asyncio
async def test_blocks_as_unverified_not_as_a_detection_when_fail_closed_defender_is_unavailable() -> (
    None
):
    def unavailable(_body: JsonObject) -> FakeResponse:
        return json_response({"title": "Service Unavailable"}, status=503)

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-3")

    async with harness(unavailable, fail_closed=True) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is False
    assert record.verdict.reason == "runtime_error:defender_unverified"
    assert record.verdict.message == (
        "Security validation is unavailable and this agent is configured to fail closed."
    )


@pytest.mark.asyncio
async def test_follows_the_fail_mode_when_the_identity_is_invalid() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-4")

    async with harness(allow, fail_closed=True, agent_id=" ") as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is False
    assert record.verdict.reason == "runtime_error:defender_unverified"
    assert h.endpoint.bodies == []
    (evaluation,) = h.evaluations
    assert evaluation.error == "evaluation failed (ValueError)"


@pytest.mark.asyncio
async def test_does_not_call_defender_for_points_it_does_not_evaluate() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-5")

    async with harness(lambda _: json_response({"decision": "deny"})) as h:
        startup = await h.emitter.emit_unchecked(builder.agent_startup(tools_registered=["Search"]))
        model_call = await h.emitter.emit_unchecked(
            builder.pre_model_call(
                model_id="gpt-4o", messages=[{"role": "user", "content": "hi"}], tools=[]
            )
        )
        shutdown = await h.emitter.emit_unchecked(builder.agent_shutdown(reason="completed"))

    assert startup.proceeds is True
    assert model_call.proceeds is True
    assert shutdown.proceeds is True
    assert h.endpoint.bodies == []
    assert h.evaluations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_follows_the_fail_mode_when_no_identity_is_resolved(fail_closed: bool) -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-6")

    async with harness(
        lambda _: json_response({"decision": "allow"}),
        fail_closed=fail_closed,
        resolve_nothing=True,
    ) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert h.endpoint.bodies == []
    (evaluation,) = h.evaluations
    assert evaluation.evaluated is False
    assert evaluation.error == "no agent identity was resolved"
    assert record.proceeds is not fail_closed
    if fail_closed:
        assert record.verdict.reason == "runtime_error:defender_unverified"
    else:
        (warning,) = record.verdict.warnings
        assert warning.reason == "defender:unverified"
        assert warning.message == "no agent identity was resolved"


@pytest.mark.asyncio
async def test_evaluates_all_four_points_of_a_turn_in_one_session() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s-7")

    async with harness(allow) as h:
        for context in (
            builder.input(content="Summarize the latest release notes"),
            builder.pre_tool_call(call_id="call-1", name="FetchPage", args={"url": THREAT_URL}),
            builder.post_tool_call(
                call_id="call-2",
                name="Search",
                args={"query": "release notes"},
                value="3 results",
            ),
            builder.output(content="Here is the summary."),
        ):
            record = await h.emitter.emit_unchecked(context)
            assert record.proceeds is True

    assert [body["interception_point"] for body in h.endpoint.bodies] == [
        "input",
        "pre_tool_call",
        "post_tool_call",
        "output",
    ]
    assert [body["sequence"] for body in h.endpoint.bodies] == [0, 1, 2, 3]
    assert len({e.correlation_id for e in h.evaluations}) == 4


@pytest.mark.asyncio
async def test_accepts_an_async_call_resolver() -> None:
    session = FakeDefenderSession(allow)
    options = DefenderRtpOptions(enabled=True, endpoint=ENDPOINT)
    tokens = TokenSource()
    seen: list[str] = []

    async def resolve_call(context: AgentContext) -> A365DefenderCall | None:
        seen.append(context["interception_point"])
        return A365DefenderCall(
            DefenderRtpAgentContext(agent_id=AGENT_ID, tenant_id=TENANT_ID), tokens.resolve
        )

    emitter = add_a365_defender(
        create_protection_emitter(defender=options),
        A365DefenderInterceptor(DefenderRtpClient(options, session), resolve_call),  # type: ignore[arg-type]
    )
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    record = await emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is True
    assert seen == ["input"]
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_a_failing_evaluation_callback_does_not_change_the_verdict() -> None:
    def failing_callback(_result: DefenderRtpEvaluationResult) -> None:
        raise RuntimeError("telemetry is down")

    session = FakeDefenderSession(lambda _: json_response({"decision": "deny"}))
    options = DefenderRtpOptions(enabled=True, endpoint=ENDPOINT)
    agent = DefenderRtpAgentContext(agent_id=AGENT_ID, tenant_id=TENANT_ID)
    emitter = add_a365_defender(
        create_protection_emitter(defender=options),
        A365DefenderInterceptor(
            DefenderRtpClient(options, session),  # type: ignore[arg-type]
            lambda _context: A365DefenderCall(agent, TokenSource().resolve),
            failing_callback,
        ),
    )
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    record = await emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is False
    assert record.verdict.reason == "defender:block"


@pytest.mark.asyncio
async def test_a_slow_evaluation_callback_does_not_hold_up_or_change_the_verdict() -> None:
    release = threading.Event()
    seen: list[DefenderRtpEvaluationResult] = []

    def slow_callback(result: DefenderRtpEvaluationResult) -> None:
        release.wait(5)
        seen.append(result)

    options = DefenderRtpOptions(enabled=True, endpoint=ENDPOINT)
    agent = DefenderRtpAgentContext(agent_id=AGENT_ID, tenant_id=TENANT_ID)
    emitter = add_a365_defender(
        create_protection_emitter(interceptor_timeout_seconds=0.5),
        A365DefenderInterceptor(
            DefenderRtpClient(options, FakeDefenderSession(allow)),  # type: ignore[arg-type]
            lambda _context: A365DefenderCall(agent, TokenSource().resolve),
            slow_callback,
        ),
    )
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    started = time.perf_counter()
    try:
        record = await emitter.emit_unchecked(builder.input(content="hello"))
        elapsed = time.perf_counter() - started
    finally:
        release.set()
        await asyncio.get_running_loop().shutdown_default_executor()

    assert record.proceeds is True
    assert record.verdict.reason is None, "not an interceptor timeout"
    assert elapsed < 0.5
    (evaluation,) = seen
    assert evaluation.evaluated is True and evaluation.allowed is True


@pytest.mark.asyncio
async def test_a_defender_warning_in_the_reserved_namespace_does_not_turn_an_allow_into_a_deny() -> (
    None
):
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")
    warnings = [
        {"reason": "host_error:upstream", "message": "Reserved."},
        {"reason": " ", "message": "Blank."},
        {"reason": "prevention_annotated", "message": "Suspicious."},
    ]

    async with harness(lambda _: json_response({"decision": "allow", "warnings": warnings})) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is True
    assert [(w.reason, w.message) for w in record.verdict.warnings] == [
        ("defender:warning", "Reserved."),
        ("defender:warning", "Blank."),
        ("prevention_annotated", "Suspicious."),
    ]


@pytest.mark.asyncio
async def test_a_defender_timeout_fails_open_before_the_emitter_times_out() -> None:
    async def hanging(_body: JsonObject) -> FakeResponse:
        await asyncio.sleep(30)
        return json_response({"decision": "deny"})

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(hanging, timeout_seconds=0.2) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is True, "fail open, not host_error:interceptor_timeout"
    assert record.verdict.reason is None
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message == "request timeout"


@pytest.mark.asyncio
async def test_a_defender_timeout_blocks_as_unverified_when_failing_closed() -> None:
    async def hanging(_body: JsonObject) -> FakeResponse:
        await asyncio.sleep(30)
        return json_response({"decision": "allow"})

    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(hanging, timeout_seconds=0.2, fail_closed=True) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is False
    assert record.verdict.reason == "runtime_error:defender_unverified"


def emitter_with(
    resolve_call: A365DefenderCallResolver,
    *,
    enabled: bool = True,
    fail_closed: bool = False,
) -> tuple[InterceptionEmitter, FakeDefenderSession]:
    session = FakeDefenderSession(allow)
    options = DefenderRtpOptions(enabled=enabled, endpoint=ENDPOINT, fail_closed=fail_closed)
    emitter = add_a365_defender(
        create_protection_emitter(defender=options),
        A365DefenderInterceptor(DefenderRtpClient(options, session), resolve_call),  # type: ignore[arg-type]
    )
    return emitter, session


@pytest.mark.asyncio
async def test_does_not_resolve_the_call_for_points_defender_does_not_evaluate() -> None:
    seen: list[str] = []

    def resolve_call(context: AgentContext) -> A365DefenderCall | None:
        seen.append(context["interception_point"])
        raise AssertionError("not expected")

    emitter, session = emitter_with(resolve_call)
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    for context in (
        builder.agent_startup(tools_registered=["Search"]),
        builder.pre_model_call(model_id="gpt-4o", messages=[{"role": "user", "content": "hi"}]),
        builder.post_model_call(
            model_id="gpt-4o", content="hi", tool_calls=[], finish_reason="stop"
        ),
        builder.agent_shutdown(reason="completed"),
    ):
        record = await emitter.emit_unchecked(context)
        assert record.proceeds is True

    assert seen == []
    assert session.calls == []


@pytest.mark.asyncio
async def test_does_not_resolve_the_call_when_disabled() -> None:
    seen: list[str] = []

    def resolve_call(context: AgentContext) -> A365DefenderCall | None:
        seen.append(context["interception_point"])
        raise AssertionError("not expected")

    emitter, session = emitter_with(resolve_call, enabled=False)
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    record = await emitter.emit_unchecked(builder.input(content="hello"))

    assert record.proceeds is True
    assert record.verdict.warnings == ()
    assert seen == []
    assert session.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_failing_call_resolver_follows_the_fail_mode(
    is_async: bool, fail_closed: bool, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(_context: AgentContext) -> A365DefenderCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    async def failing_async(_context: AgentContext) -> A365DefenderCall | None:
        raise RuntimeError("no turn context; password=hunter2")

    emitter, session = emitter_with(failing_async if is_async else failing, fail_closed=fail_closed)
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    with caplog.at_level(logging.WARNING):
        record = await emitter.emit_unchecked(builder.input(content="hello"))

    assert session.calls == []
    assert not (record.verdict.reason or "").startswith("host_error:")
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message == "evaluation failed (RuntimeError)", "only the type reaches the record"
    assert "hunter2" not in repr(record)
    assert any("hunter2" in (entry.exc_text or "") for entry in caplog.records), "it is logged"
    if fail_closed:
        assert record.proceeds is False
        assert record.verdict.reason == "runtime_error:defender_unverified"
    else:
        assert record.proceeds is True


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_failing_token_resolver_follows_the_fail_mode(fail_closed: bool) -> None:
    async def failing_tokens(_agent_id: str, _tenant_id: str, _scopes: list[str]) -> str | None:
        raise RuntimeError("no credential")

    agent = DefenderRtpAgentContext(agent_id=AGENT_ID, tenant_id=TENANT_ID)
    emitter, session = emitter_with(
        lambda _context: A365DefenderCall(agent, failing_tokens), fail_closed=fail_closed
    )
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    record = await emitter.emit_unchecked(builder.input(content="hello"))

    assert session.calls == []
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message == "entra token unavailable"
    assert record.proceeds is not fail_closed
    if fail_closed:
        assert record.verdict.reason == "runtime_error:defender_unverified"


PADDING = "a" * 20000
TRUNCATED_ERROR = "content exceeded max_content_characters; Defender evaluated a truncated copy"


def deny_block_me(body: JsonObject) -> FakeResponse:
    if "BLOCK_ME" in str(body["target"]):
        return json_response({"decision": "deny", "reason": "prevention_blocked"})
    return json_response({"decision": "allow"})


@pytest.mark.asyncio
async def test_padding_past_the_limit_blocks_as_unverified_when_failing_closed() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(deny_block_me, fail_closed=True) as h:
        record = await h.emitter.emit_unchecked(builder.input(content=PADDING + "BLOCK_ME"))

    assert record.proceeds is False
    assert record.verdict.reason == "runtime_error:defender_unverified"
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message == TRUNCATED_ERROR
    (evaluation,) = h.evaluations
    assert evaluation.truncated is True and evaluation.evaluated is True


@pytest.mark.asyncio
async def test_padding_past_the_limit_is_allowed_with_a_warning_when_failing_open() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(deny_block_me) as h:
        record = await h.emitter.emit_unchecked(builder.input(content=PADDING + "BLOCK_ME"))

    assert record.proceeds is True
    (warning,) = record.verdict.warnings
    assert warning.reason == "defender:unverified"
    assert warning.message == TRUNCATED_ERROR


@pytest.mark.asyncio
async def test_a_defender_deny_of_truncated_content_blocks_even_when_failing_open() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(deny_block_me) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="BLOCK_ME" + PADDING))

    assert record.proceeds is False
    assert record.verdict.reason == "defender:block:prevention_blocked"


def transform_everything(_body: JsonObject) -> FakeResponse:
    return json_response({
        "decision": "transform",
        "transform": {"path": "/target", "value": "[redacted]"},
    })


@pytest.mark.asyncio
async def test_a_defender_transform_of_truncated_content_blocks_even_when_failing_open() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(transform_everything) as h:
        record = await h.emitter.emit_unchecked(builder.input(content=PADDING + "secret"))

    assert record.proceeds is False
    assert record.verdict.reason == "defender:block"
    (evaluation,) = h.evaluations
    assert evaluation.truncated is True
    assert evaluation.verified is True


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_closed", [False, True])
async def test_a_called_tool_not_among_the_declarations_searched_follows_the_fail_mode(
    fail_closed: bool,
) -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")
    context = builder.pre_tool_call(call_id="call-1", name="Search", args={"query": "q"})
    context["tools"] = [{"name": f"tool{i}"} for i in range(10_000)] + [{"name": "Search"}]

    async with harness(allow, fail_closed=fail_closed) as h:
        record = await h.emitter.emit_unchecked(context)

    assert record.proceeds is not fail_closed
    (evaluation,) = h.evaluations
    assert evaluation.truncated is True
    if fail_closed:
        assert record.verdict.reason == "runtime_error:defender_unverified"
    else:
        (warning,) = record.verdict.warnings
        assert warning.reason == "defender:unverified"
        assert warning.message == (
            "the called tool was not among the first 10000 tool declarations; Defender "
            "evaluated without its declaration"
        )


@pytest.mark.asyncio
async def test_content_within_the_limit_is_allowed_without_warnings() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(deny_block_me) as h:
        record = await h.emitter.emit_unchecked(builder.input(content="a harmless message"))

    assert record.proceeds is True
    assert record.verdict.warnings == ()


@pytest.mark.asyncio
async def test_a_lone_surrogate_in_emitted_content_never_fails_open() -> None:
    builder = AgentContextBuilder(agent_id=AGENT_ID, framework="agent-framework", session_id="s")

    async with harness(deny_block_me) as h:
        record = await h.emitter.emit_unchecked(
            builder.pre_tool_call(call_id="call-1", name="Run", args={"text": "\ud800BLOCK_ME"})
        )

    # agent-hooks may reject the context itself; when it passes it on, Defender evaluates the
    # normalized text. Either way the default fail-open mode does not allow it.
    assert record.proceeds is False
    assert all(evaluation.evaluated for evaluation in h.evaluations)


def test_maps_an_allow_of_a_truncated_copy_to_an_unverified_verdict() -> None:
    result = DefenderRtpEvaluationResult(
        allowed=True,
        evaluated=True,
        truncated=True,
        error=TRUNCATED_ERROR,
        verdict=DefenderRtpVerdict(
            warnings=(DefenderRtpWarning("prevention_annotated", "Suspicious."),),
            result_labels=("MaliciousUrl",),
        ),
    )

    verdict = A365DefenderInterceptor.to_verdict(result)

    assert result.verified is False
    assert verdict.decision is Decision.ALLOW
    assert [(w.reason, w.message) for w in verdict.warnings] == [
        ("defender:unverified", TRUNCATED_ERROR),
        ("prevention_annotated", "Suspicious."),
    ]
    assert verdict.result_labels == ("MaliciousUrl",)


def test_creates_an_enforcing_strictest_emitter_with_room_for_the_defender_timeout() -> None:
    emitter = create_protection_emitter(defender=DefenderRtpOptions(timeout_seconds=3))

    assert emitter.mode is EnforcementMode.ENFORCE
    assert emitter.composition == CompositionConfig.strictest(SynthesisPolicy.DENY)
    assert emitter._timeout == 5.0
    assert create_protection_emitter()._timeout == 12.0
    assert create_protection_emitter(interceptor_timeout_seconds=1.5)._timeout == 1.5


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, -1.0, True])
def test_rejects_an_interceptor_timeout_that_is_not_positive_and_finite(timeout: float) -> None:
    with pytest.raises(ValueError, match="interceptor_timeout_seconds"):
        create_protection_emitter(interceptor_timeout_seconds=timeout)


@pytest.mark.parametrize("defender_timeout", [float("nan"), float("inf"), -2.0, -5.0])
def test_rejects_a_defender_timeout_that_leaves_no_interceptor_timeout(
    defender_timeout: float,
) -> None:
    with pytest.raises(ValueError, match="interceptor_timeout_seconds"):
        create_protection_emitter(defender=DefenderRtpOptions(timeout_seconds=defender_timeout))


def test_registers_the_interceptor_under_the_defender_name() -> None:
    interceptor = A365DefenderInterceptor(
        DefenderRtpClient(DefenderRtpOptions()), lambda _context: None
    )

    emitter = add_a365_defender(create_protection_emitter(), interceptor)

    assert emitter._interceptors == [interceptor]
    assert emitter._names == ["defender"]
    assert A365DefenderInterceptor.NAME == "defender"

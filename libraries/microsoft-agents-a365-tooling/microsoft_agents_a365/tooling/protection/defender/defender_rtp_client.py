# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Client for the Microsoft Defender for AI prevention endpoint."""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import functools
import inspect
import itertools
import json
import logging
import math
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import aiohttp

from ._http import http_session
from .defender_rtp_agent_context import DefenderRtpAgentContext, DefenderRtpTokenResolver
from .defender_rtp_evaluation_result import (
    DefenderRtpEvaluationResult,
    DefenderRtpVerdict,
    DefenderRtpWarning,
)
from .defender_rtp_options import DefenderRtpOptions, is_https_url

logger = logging.getLogger(__name__)

JsonObject = dict[str, object]
"""A JSON object as parsed by :mod:`json`."""

_TokenKey = tuple[str, str, str]

_DEFAULT_FRAMEWORK: Final[str] = "agent365"
_A365_EXTENSION: Final[str] = "a365"
_MAX_ERROR_DETAIL_CHARACTERS: Final[int] = 200
_MAX_CACHED_TOKENS: Final[int] = 100
_MAX_TRACKED_SESSIONS: Final[int] = 1000
_TOKEN_REFRESH_SKEW_SECONDS: Final[float] = 300.0
_EVALUATED_POINTS: Final[frozenset[str]] = frozenset(
    {"input", "pre_tool_call", "post_tool_call", "output"}
)
_ACTOR_KINDS: Final[frozenset[str]] = frozenset({"human", "service", "agent"})
# Envelope members and members with dedicated handling; any other member of the context is
# content.
_KNOWN_MEMBERS: Final[frozenset[str]] = frozenset(
    {
        "spec",
        "interception_point",
        "timestamp",
        "sequence",
        "request_id",
        "session",
        "agent",
        "tenant",
        "actor",
        "model",
        "trace",
        "input",
        "output",
        "target",
        "tool_call",
        "tool_result",
        "messages",
        "tools",
        "extensions",
    }
)
# A fitted copy carries at most this many times max_content_characters of content in all.
_CONTENT_BUDGET_FACTOR: Final[int] = 4
# At a tool point, the called tool's declaration is searched for among this many entries.
_MAX_TOOL_SCAN: Final[int] = 10_000
# Containers nested deeper are cut, well within the nesting a JSON parser accepts.
_MAX_DEPTH: Final[int] = 32
_OMITTED: Final[object] = object()
# Ends a cut string whose omitted length is not known without unbounded work.
_UNCOUNTED_MARKER: Final[str] = "...[truncated]"
_CONTENT_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_SURROGATES = re.compile("[\ud800-\udfff]")
_EXTENSION_KEY = re.compile(r"[a-z][a-z0-9_]*")
_INVALID_FRAMEWORK_CHARACTERS = re.compile(r"[^a-z0-9_-]+")
_WHITESPACE = re.compile(r"\s+")
_FAIL_CLOSED_BLOCK_REASON: Final[str] = (
    "Security validation is unavailable and this agent is configured to fail closed."
)
_TRANSFORM_BLOCK_REASON: Final[str] = (
    "Microsoft Defender for AI asked to rewrite this content, which this SDK version does not "
    "apply yet."
)
_DENY_BLOCK_REASON: Final[str] = "Blocked by Microsoft Defender for AI."
_TRUNCATED_ERROR: Final[str] = (
    "content exceeded max_content_characters; Defender evaluated a truncated copy"
)
_TRUNCATED_TOOL_ERROR: Final[str] = (
    "the called tool's declaration exceeded max_content_characters; Defender evaluated a "
    "truncated copy"
)
_UNSCANNED_TOOL_ERROR: Final[str] = (
    f"the called tool was not among the first {_MAX_TOOL_SCAN} tool declarations; Defender "
    "evaluated without its declaration"
)
_TRUNCATED_BLOCK_REASON: Final[str] = (
    "The content is longer than Microsoft Defender for AI evaluates, and this agent is "
    "configured to fail closed."
)


@dataclass(frozen=True)
class _CachedToken:
    token: str
    expires_at: float


class DefenderRtpClient:
    """Client for the Microsoft Defender for AI prevention endpoint
    (``POST .../v1/protection/evaluate``).

    Defender evaluates four agent-hooks/0.1 interception points: ``input`` (the user's message,
    before the agent runs), ``pre_tool_call``, ``post_tool_call``, and ``output`` (the reply,
    before it is sent). :meth:`evaluate_hook_context` sends Defender a fitted copy of a context
    emitted by an agent-hooks host (normalized to Defender's request validation and clamped,
    keeping its session, sequence and tool call ids) and returns the verdict. Each call carries
    a unique ``x-ms-correlation-id``.
    """

    AGENT_HOOKS_SPEC: Final[str] = "agent-hooks/0.1"
    """The only agent-hooks wire version the prevention endpoint accepts."""

    CORRELATION_ID_HEADER: Final[str] = "x-ms-correlation-id"
    """The header Defender logs each evaluation under."""

    def __init__(
        self,
        options: DefenderRtpOptions,
        session: aiohttp.ClientSession | None = None,
        *,
        id_factory: Callable[[], uuid.UUID] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            options: The Defender configuration, for example
                :meth:`DefenderRtpOptions.from_environment`.
            session: The HTTP session; a pooled session owned by the caller is recommended.
                When omitted, each call opens and closes its own session.
            id_factory: Creates correlation ids (tests).
            clock: Returns the current time in seconds since the epoch (tests).

        Raises:
            ValueError: If the options cannot be used for an enabled client.
        """
        # A private copy: later changes to the caller's options (for example an http://
        # endpoint) cannot bypass the validation below.
        self._options = dataclasses.replace(options)
        self._options.validate()
        self._session = session
        self._id_factory = id_factory or uuid.uuid4
        self._clock = clock or time.time
        self._tokens: dict[_TokenKey, _CachedToken] = {}
        self._in_flight_tokens: dict[_TokenKey, asyncio.Future[str]] = {}
        self._sequences: dict[str, int] = {}
        # The highest sequence of any session no longer tracked: an untracked session resumes
        # above it, so a generated sequence never repeats or decreases within a session.
        self._untracked_high_water = 0

    @property
    def options(self) -> DefenderRtpOptions:
        """A copy of the configuration this client uses."""
        return dataclasses.replace(self._options)

    @staticmethod
    def is_evaluated_interception_point(interception_point: str | None) -> bool:
        """Whether Defender evaluates the given agent-hooks interception point.

        Args:
            interception_point: The agent-hooks interception point, for example
                ``pre_tool_call``.

        Returns:
            True for ``input``, ``pre_tool_call``, ``post_tool_call`` and ``output``.
        """
        return isinstance(interception_point, str) and interception_point in _EVALUATED_POINTS

    async def evaluate_hook_context(
        self,
        context: Mapping[str, object],
        agent: DefenderRtpAgentContext,
        token_resolver: DefenderRtpTokenResolver,
    ) -> DefenderRtpEvaluationResult | None:
        """Evaluate an agent-hooks context with Defender. The context is not modified.

        Defender receives a fitted copy, normalized to its request validation: the envelope
        (agent, session, tenant, actor, ids, roles and names) is kept whole, each content string
        is clamped to :attr:`DefenderRtpOptions.max_content_characters`, all content shares a
        budget of four times that (the content under decision, which is sent twice, may use
        half of it), and every string is valid Unicode. When the content under decision does
        not fit, Defender evaluates the cut copy: its deny still blocks, but its allow follows
        the fail mode (``truncated``). So does an allow at a tool point when the called tool's
        declaration had to be cut, or was not among the first 10,000 tool declarations.
        Token acquisition and the request share one deadline,
        :attr:`DefenderRtpOptions.timeout_seconds`, so the fail mode applies within that time.

        Args:
            context: The agent-hooks/0.1 context emitted by the host.
            agent: The agent identity and turn; fills fields the context does not set.
            token_resolver: Resolves the agent identity's Defender token.

        Returns:
            The result, or ``None`` when Defender RTP is disabled or the point is not one
            Defender evaluates.

        Raises:
            ValueError: If the agent identity, the tenant, ``agent.id``, ``session.id`` or a
                tool call's name is missing, or the context is not JSON.
        """
        if not self._options.enabled:
            return None

        if not isinstance(context, Mapping):
            raise TypeError("context must be an agent-hooks context mapping.")

        if not callable(token_resolver):
            raise TypeError("token_resolver must be callable.")

        point = _read_string(context.get("interception_point"))
        if point is None or not self.is_evaluated_interception_point(point):
            return None

        deadline = asyncio.get_running_loop().time() + self._options.timeout_seconds
        started = time.perf_counter()
        _require_string(agent.agent_id, "agent_id")
        _require_string(agent.tenant_id, "tenant_id")
        hook, truncation = self._prepare(context, agent)
        body = _serialize(hook)
        session_id = _read_string(_get(hook.get("session"), "id"))

        token: str | None
        try:
            async with asyncio.timeout_at(deadline):
                token = await self._get_access_token(agent, token_resolver)
        except Exception as error:
            logger.warning(
                "Defender RTP token acquisition failed: %s", str(error) or type(error).__name__
            )
            token = None

        if not token:
            return self.unavailable(
                point,
                "entra token unavailable",
                session_id,
                None,
                time.perf_counter() - started,
            )

        return await self._post(body, point, session_id, token, started, deadline, truncation)

    async def prefetch_access_token(
        self,
        agent: DefenderRtpAgentContext,
        token_resolver: DefenderRtpTokenResolver,
    ) -> None:
        """Acquire and cache the agent identity's Defender token without evaluating anything.

        The first evaluation then does not wait for Entra. A cached token is used until it
        expires; within five minutes of expiry, a call refreshes it in the background, and a
        failed refresh keeps the cached token in use.

        Args:
            agent: The agent identity and tenant.
            token_resolver: Resolves the agent identity's Defender token.

        Raises:
            ValueError: If the agent identity or the tenant is missing.
            Exception: If no token can be acquired.
        """
        if not self._options.enabled:
            return

        if not callable(token_resolver):
            raise TypeError("token_resolver must be callable.")

        _require_string(agent.agent_id, "agent_id")
        _require_string(agent.tenant_id, "tenant_id")
        await self._get_access_token(agent, token_resolver)

    def unavailable(
        self,
        interception_point: str,
        error: str,
        session_id: str | None = None,
        http_status: int | None = None,
        latency_seconds: float = 0.0,
    ) -> DefenderRtpEvaluationResult:
        """A result for an evaluation that could not be made, for example an invalid context.

        It follows :attr:`DefenderRtpOptions.fail_closed`, like a transport failure.

        Args:
            interception_point: The agent-hooks interception point.
            error: Why no verdict was obtained.
            session_id: The agent-hooks session id, when known.
            http_status: The HTTP status, when a response was received.
            latency_seconds: Time spent before the failure, in seconds.

        Returns:
            The not-evaluated result.
        """
        return self._not_evaluated(
            interception_point,
            str(self._id_factory()),
            session_id,
            error,
            http_status,
            latency_seconds,
        )

    # ---- agent-hooks context -------------------------------------------------------------

    def _prepare(
        self, context: Mapping[str, object], agent: DefenderRtpAgentContext
    ) -> tuple[JsonObject, str | None]:
        """A fitted copy of the context that meets Defender's request validation and size limits.

        ``target`` equals the point's field, ``tool_call`` and ``tool_result`` carry only spec
        members, the timestamp is UTC, and loosely filled optional fields are repaired or
        dropped; a member of an unexpected shape is ignored. The envelope (the agent,
        session, tenant, actor, request, model and trace, and roles, tool names and ids) is
        built from its spec fields alone and not clamped, so the request validates and
        correlates whatever the limit. Each content string is cut to
        ``max_content_characters``, and all content shares a budget of
        ``_CONTENT_BUDGET_FACTOR`` times that. The content under decision is sent twice (as the
        point's field and as ``target``), so it may use half of the budget; the rest goes, in
        order, to the called tool's declaration, the call's arguments at ``post_tool_call``,
        the other tool declarations, the most recent messages, extensions, and any other
        member. Every string is valid Unicode. The copy is built from the context without
        copying it whole; the context is not modified.

        Returns:
            The copy, and why Defender's allow of it would not cover what the host acts on, or
            ``None``: the content under decision (``target``, which equals the point's field)
            was cut to fit, or at a tool point the called tool's declaration was cut or not
            among the entries searched (see :func:`_fit_called_tool`).
        """
        point = _read_string(context.get("interception_point"))
        agent_node = context.get("agent")
        agent_id = _require_string(
            _first_non_empty(
                agent.agent_object_id, _read_string(_get(agent_node, "id")), agent.agent_id
            ),
            "agent.id",
        )
        # The envelope is built from its spec fields alone, kept whole: nothing else a host puts
        # in an envelope object is copied, so it cannot escape the content budget.
        session = context.get("session")
        session_id = _require_string(_read_string(_get(session, "id")), "session.id")
        sequence = context.get("sequence")
        if isinstance(sequence, int) and _is_non_negative_integer(sequence):
            self._observe_sequence(session_id, sequence)
        else:
            sequence = self._next_sequence(session_id)

        prepared_session: JsonObject = {"id": _normalize(session_id)}
        started_at = _parse_timestamp(_get(session, "started_at"))
        if started_at is not None:
            prepared_session["started_at"] = _format_utc(started_at)

        turn = _get(session, "turn")
        if isinstance(turn, int) and _is_non_negative_integer(turn):
            prepared_session["turn"] = turn

        prepared_agent: JsonObject = {
            "id": _normalize(agent_id),
            "framework": _sanitize_framework(
                _first_non_empty(_read_string(_get(agent_node, "framework")), agent.framework)
            ),
        }
        name = _first_non_empty(_read_string(_get(agent_node, "name")), agent.agent_name)
        if name is not None:
            prepared_agent["name"] = _normalize(name)

        version = _read_string(_get(agent_node, "version"))
        if version:
            prepared_agent["version"] = _normalize(version)

        # The token is issued in the agent's tenant, and Defender requires tenant.id to equal
        # the token's tid, so the agent's tenant is authoritative: a different host value would
        # only be rejected, and a rejection follows the fail mode.
        tenant = context.get("tenant")
        host_tenant_id = _read_string(_get(tenant, "id"))
        if host_tenant_id and host_tenant_id != agent.tenant_id:
            logger.warning(
                "Defender RTP: the context's tenant.id is not the agent's tenant; sending the "
                "agent's tenant, which the token is issued for."
            )
        prepared_tenant: JsonObject = {"id": _normalize(agent.tenant_id)}
        tenant_name = _read_string(_get(tenant, "name"))
        if tenant_name:
            prepared_tenant["name"] = _normalize(tenant_name)

        hook: JsonObject = {
            "spec": self.AGENT_HOOKS_SPEC,
            "interception_point": point,
            "timestamp": self._utc_timestamp(context.get("timestamp")),
            "sequence": sequence,
            "agent": prepared_agent,
            "session": prepared_session,
            "tenant": prepared_tenant,
        }

        actor = context.get("actor")
        if actor is None and agent.user_id:
            actor = {
                "id": agent.user_id,
                "kind": agent.actor_kind if agent.actor_kind is not None else "human",
            }

        if isinstance(actor, dict):
            prepared_actor: JsonObject = {}
            actor_id = _read_string(actor.get("id"))
            if actor_id:
                prepared_actor["id"] = _normalize(actor_id)

            kind = _read_string(actor.get("kind"))
            if kind in _ACTOR_KINDS:
                prepared_actor["kind"] = kind

            hook["actor"] = prepared_actor

        request_id = context.get("request_id")
        if request_id is None:
            request_id = agent.request_id or None

        if isinstance(request_id, str):
            hook["request_id"] = _normalize(request_id)

        model = context.get("model")
        if model is None and agent.model_name:
            model = {"id": agent.model_name}

        model_id = _read_string(_get(model, "id"))
        if model_id:
            hook["model"] = {"id": _normalize(model_id)}

        trace = context.get("trace")
        if isinstance(trace, dict):
            prepared_trace: JsonObject = {}
            for key in ("trace_id", "span_id"):
                value = _read_string(trace.get(key))
                if value:
                    prepared_trace[key] = _normalize(value)

            if prepared_trace:
                hook["trace"] = prepared_trace

        max_characters = self._options.max_content_characters
        budget = max_characters * _CONTENT_BUDGET_FACTOR
        # The content under decision is sent twice, as the point's field and as target, so it
        # may use half of the budget.
        decision = _Fitter(max_characters, budget // 2)
        tool_call = context.get("tool_call")
        tool_name: str | None = None
        called: JsonObject | None = None
        if point == "input":
            input_node = context.get("input")
            role = _read_string(_get(input_node, "role"))
            content, truncated = decision.fit(_content_of(input_node), "")
            prepared_input: JsonObject = {
                "content": content,
                "role": role if role in ("system", "external") else "user",
            }
            hook["input"] = prepared_input
            hook["target"] = prepared_input
        elif point == "output":
            content, truncated = decision.fit(_content_of(context.get("output")), "")
            prepared_output: JsonObject = {"content": content}
            hook["output"] = prepared_output
            hook["target"] = prepared_output
        else:
            tool_name = _require_string(_read_string(_get(tool_call, "name")), "tool_call.name")
            called = {
                "id": _normalize(
                    _first_non_empty(_read_string(_get(tool_call, "id")))
                    or self._generated_tool_call_id()
                ),
                "name": _normalize(tool_name),
                "args": {},
            }
            content_hash = _get(tool_call, "content_hash")
            if isinstance(content_hash, str) and _CONTENT_HASH.fullmatch(content_hash):
                called["content_hash"] = content_hash

            hook["tool_call"] = called
            if point == "pre_tool_call":
                args, truncated = decision.fit(_to_arguments(_get(tool_call, "args")), {})
                called["args"] = args
                hook["target"] = args
            else:
                tool_result = context.get("tool_result")
                value, truncated = decision.fit(_get(tool_result, "value"), None)
                prepared_result: JsonObject = {
                    "value": value,
                    "is_error": _get(tool_result, "is_error") is True,
                }
                duration = _get(tool_result, "duration_ms")
                if _is_duration(duration):
                    prepared_result["duration_ms"] = duration

                hook["tool_result"] = prepared_result
                hook["target"] = value

        # The rest of the context shares what the content under decision leaves, in order: the
        # called tool's declaration, which Defender's verdict also depends on; the call's
        # arguments at post_tool_call, which Defender decided on at pre_tool_call; the other
        # declarations; the newest messages; extensions; and any other member. Apart from the
        # called tool's declaration, what is cut here does not change the authority of the
        # verdict.
        fitter = _Fitter(max_characters, budget - 2 * decision.used)
        declared = context.get("tools")
        tools: list[object] = []
        called_index: int | None = None
        tool_truncation: str | None = None
        if tool_name is not None:
            called_tool, called_index, tool_truncation = _fit_called_tool(
                fitter,
                declared if isinstance(declared, list) else [],
                tool_name,
                context.get("extensions"),
            )
            if called_tool is not None:
                tools.append(called_tool)

        if point == "post_tool_call" and called is not None:
            called["args"], _ = fitter.fit(_to_arguments(_get(tool_call, "args")), {})

        tools += _fit_other_tools(
            fitter, declared if isinstance(declared, list) else [], called_index
        )
        if tools:
            hook["tools"] = tools

        messages = _fit_messages(fitter, context.get("messages"))
        if messages:
            hook["messages"] = messages

        extensions = context.get("extensions")
        if isinstance(extensions, dict):
            prepared_extensions: JsonObject = {}
            # Each namespace kept costs at least one character, so only as many are read as the
            # budget could hold.
            for key, extension in itertools.islice(extensions.items(), fitter.remaining):
                if _is_extension_key(key) and not fitter.fit_member(
                    prepared_extensions, key, extension
                ):
                    break

            if prepared_extensions:
                hook["extensions"] = prepared_extensions

        for key, member in context.items():
            if key not in _KNOWN_MEMBERS and not fitter.fit_member(hook, key, member):
                break

        return hook, _TRUNCATED_ERROR if truncated else tool_truncation

    # ---- transport -----------------------------------------------------------------------

    async def _post(
        self,
        body: bytes,
        point: str,
        session_id: str | None,
        access_token: str,
        started: float,
        deadline: float,
        truncation: str | None = None,
    ) -> DefenderRtpEvaluationResult:
        correlation_id = str(self._id_factory())
        endpoint = self._options.endpoint
        if not endpoint or not is_https_url(endpoint):
            return self._failure(
                point, correlation_id, session_id, "no HTTPS endpoint configured", None, started
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            self.CORRELATION_ID_HEADER: correlation_id,
        }
        status: int | None = None
        raw: bytes | None = None
        error: str | None = None
        try:
            async with asyncio.timeout_at(deadline):
                async with http_session(self._session) as session:
                    # No redirects: a 307/308 would resend the context and the token to a
                    # target that never passed the HTTPS check; a 3xx follows the fail mode.
                    async with session.post(
                        endpoint,
                        data=body,
                        headers=headers,
                        allow_redirects=False,
                    ) as response:
                        status = response.status
                        try:
                            raw = await response.read()
                        except TimeoutError:
                            raise
                        except Exception as read_error:
                            logger.debug("Defender RTP response read failed: %r", read_error)
                            error = "response body could not be read"
        except TimeoutError:
            error = "request timeout"
        except aiohttp.ClientError:
            error = "request failed"
        except Exception as send_error:
            # Any failure that is not the caller's cancellation (for example from a retry or
            # circuit-breaker session) is not a verdict: it follows the fail mode.
            error = f"request failed: {type(send_error).__name__}"

        if error is not None or status is None or raw is None:
            return self._failure(
                point, correlation_id, session_id, error or "request failed", status, started
            )

        text = raw.decode("utf-8", errors="replace")
        if not 200 <= status < 300:
            detail = _error_detail(text)
            error = f"http {status}: {detail}" if detail else f"http {status}"
            return self._failure(point, correlation_id, session_id, error, status, started)

        try:
            payload: object = json.loads(text)
        except (ValueError, RecursionError):
            return self._failure(
                point, correlation_id, session_id, "non-JSON response", status, started
            )

        verdict = _parse_verdict(payload)
        if verdict is None:
            return self._failure(
                point, correlation_id, session_id, "response contained no verdict", status, started
            )

        allowed = verdict.decision == "allow"
        block_reason: str | None = None
        if not allowed:
            # transform also blocks: the rewrite cannot be applied here, and releasing the
            # original content would defeat it.
            block_reason = (
                _TRANSFORM_BLOCK_REASON
                if verdict.decision == "transform"
                else verdict.message or _DENY_BLOCK_REASON
            )

        logger.debug(
            "Defender RTP %s: decision=%s labels=%s x-ms-correlation-id=%s",
            point,
            verdict.decision,
            ",".join(verdict.result_labels) or "-",
            correlation_id,
        )
        if truncation is not None and allowed:
            # Defender evaluated a truncated copy; its allow does not cover what was cut, which
            # the host would still act on. A block stays authoritative.
            fail_closed = self._options.fail_closed
            logger.warning(
                "Defender RTP %s: %s (%s), x-ms-correlation-id=%s",
                point,
                truncation,
                "blocked" if fail_closed else "allowed",
                correlation_id,
            )
            return DefenderRtpEvaluationResult(
                allowed=not fail_closed,
                evaluated=True,
                interception_point=point,
                correlation_id=correlation_id,
                session_id=session_id,
                verdict=verdict,
                http_status=status,
                error=truncation,
                latency_seconds=time.perf_counter() - started,
                block_reason=_TRUNCATED_BLOCK_REASON if fail_closed else None,
                truncated=True,
            )

        return DefenderRtpEvaluationResult(
            allowed=allowed,
            evaluated=True,
            interception_point=point,
            correlation_id=correlation_id,
            session_id=session_id,
            verdict=verdict,
            http_status=status,
            latency_seconds=time.perf_counter() - started,
            block_reason=block_reason,
            truncated=truncation is not None,
        )

    def _failure(
        self,
        point: str,
        correlation_id: str,
        session_id: str | None,
        error: str,
        http_status: int | None,
        started: float,
    ) -> DefenderRtpEvaluationResult:
        return self._not_evaluated(
            point,
            correlation_id,
            session_id,
            error,
            http_status,
            time.perf_counter() - started,
        )

    def _not_evaluated(
        self,
        point: str,
        correlation_id: str,
        session_id: str | None,
        error: str,
        http_status: int | None,
        latency_seconds: float,
    ) -> DefenderRtpEvaluationResult:
        fail_closed = self._options.fail_closed
        logger.warning(
            "Defender RTP %s was not evaluated (%s), x-ms-correlation-id=%s: %s",
            point,
            "blocked" if fail_closed else "allowed",
            correlation_id,
            error,
        )
        return DefenderRtpEvaluationResult(
            allowed=not fail_closed,
            evaluated=False,
            interception_point=point,
            correlation_id=correlation_id,
            session_id=session_id,
            http_status=http_status,
            error=error,
            latency_seconds=latency_seconds,
            block_reason=_FAIL_CLOSED_BLOCK_REASON if fail_closed else None,
        )

    # ---- authentication ------------------------------------------------------------------

    async def _get_access_token(
        self,
        agent: DefenderRtpAgentContext,
        token_resolver: DefenderRtpTokenResolver,
    ) -> str:
        scope = self._options.authentication_scope
        key: _TokenKey = (agent.tenant_id, agent.agent_id, scope)
        cached = self._tokens.get(key)
        now = self._clock()
        if cached is not None and now < cached.expires_at:
            if now >= cached.expires_at - _TOKEN_REFRESH_SKEW_SECONDS:
                # Refresh ahead without waiting: the cached token stays in use until it
                # expires, including when the refresh fails.
                refresh, started = self._acquisition(key, agent, token_resolver, scope)
                if started:
                    refresh.add_done_callback(_log_failed_refresh)

            return cached.token

        acquisition, _ = self._acquisition(key, agent, token_resolver, scope)
        return await asyncio.shield(acquisition)

    def _acquisition(
        self,
        key: _TokenKey,
        agent: DefenderRtpAgentContext,
        token_resolver: DefenderRtpTokenResolver,
        scope: str,
    ) -> tuple[asyncio.Future[str], bool]:
        """The in-flight acquisition for ``key``, and whether this call started it.

        One acquisition per agent, tenant and scope; it is bounded by the configured timeout,
        not tied to any single caller's cancellation, and dropped when it completes.
        """
        acquisition = self._in_flight_tokens.get(key)
        if acquisition is not None:
            return acquisition, False

        acquisition = asyncio.ensure_future(self._acquire_token(key, agent, token_resolver, scope))
        self._in_flight_tokens[key] = acquisition
        acquisition.add_done_callback(functools.partial(self._acquisition_done, key))
        return acquisition, True

    def _acquisition_done(self, key: _TokenKey, acquisition: asyncio.Future[str]) -> None:
        if self._in_flight_tokens.get(key) is acquisition:
            del self._in_flight_tokens[key]

        # Every caller may have been cancelled; retrieve the failure so it is not reported as
        # never retrieved.
        if not acquisition.cancelled():
            acquisition.exception()

    async def _acquire_token(
        self,
        key: _TokenKey,
        agent: DefenderRtpAgentContext,
        token_resolver: DefenderRtpTokenResolver,
        scope: str,
    ) -> str:
        async with asyncio.timeout(self._options.timeout_seconds):
            token = await _resolve_token(token_resolver, agent.agent_id, agent.tenant_id, [scope])

        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("The Defender token resolver returned no token.")

        expires_at = _read_expiry(token)
        if expires_at is not None:
            now = self._clock()
            if expires_at <= now:
                raise RuntimeError("The Defender token resolver returned an expired token.")

            if len(self._tokens) >= _MAX_CACHED_TOKENS:
                for stale in [k for k, v in self._tokens.items() if v.expires_at <= now]:
                    del self._tokens[stale]

                if len(self._tokens) >= _MAX_CACHED_TOKENS:
                    del self._tokens[min(self._tokens, key=lambda k: self._tokens[k].expires_at)]

            self._tokens[key] = _CachedToken(token, expires_at)

        return token

    # ---- helpers -------------------------------------------------------------------------

    def _next_sequence(self, session_id: str) -> int:
        following = self._sequence_high_water(session_id) + 1
        self._track_sequence(session_id, following)
        return following

    def _observe_sequence(self, session_id: str, sequence: int) -> None:
        """Record a host-set sequence, so a later generated one stays above it."""
        self._track_sequence(session_id, max(self._sequence_high_water(session_id), sequence))

    def _sequence_high_water(self, session_id: str) -> int:
        """The highest sequence seen in the session, which stops being tracked until recorded.

        A session that is not tracked may have been dropped from the bounded cache, so its
        sequences resume above those of every dropped session.
        """
        tracked = self._sequences.pop(session_id, None)
        return tracked if tracked is not None else self._untracked_high_water

    def _track_sequence(self, session_id: str, high_water: int) -> None:
        self._sequences[session_id] = high_water
        while len(self._sequences) > _MAX_TRACKED_SESSIONS:
            dropped = self._sequences.pop(next(iter(self._sequences)))
            self._untracked_high_water = max(self._untracked_high_water, dropped)

    def _generated_tool_call_id(self) -> str:
        return "tooluse_" + self._id_factory().hex[:12]

    def _utc_timestamp(self, value: object) -> str:
        return _format_utc(_parse_timestamp(value) or datetime.fromtimestamp(self._clock(), tz=UTC))


async def _resolve_token(
    token_resolver: DefenderRtpTokenResolver, agent_id: str, tenant_id: str, scopes: list[str]
) -> object:
    """The token from ``token_resolver``, which may be sync or async.

    A synchronous resolver (for example one that calls MSAL directly) would block the event
    loop, where the deadline cannot interrupt it, so it runs on a worker thread.
    """
    if inspect.iscoroutinefunction(token_resolver):
        resolved: object = token_resolver(agent_id, tenant_id, scopes)
    else:
        resolved = await asyncio.to_thread(token_resolver, agent_id, tenant_id, scopes)

    return await resolved if inspect.isawaitable(resolved) else resolved


def _log_failed_refresh(refresh: asyncio.Future[str]) -> None:
    if not refresh.cancelled() and refresh.exception() is not None:
        logger.warning(
            "Defender RTP token refresh failed; the cached token is used until it expires: %s",
            refresh.exception(),
        )


class _Fitter:
    """Copies JSON content into the request within a per-string limit and a shared budget.

    A string is cut to ``max_characters`` (truncation marker included) and to the budget left.
    Each string, key, number and kept-whole name costs its length in characters and every
    other value one; once the budget is spent nothing more is copied, so the copy and the time
    to build it stay bounded whatever the host passes. Strings and keys are made valid
    Unicode, non-finite numbers become text, and containers nested deeper than ``_MAX_DEPTH``
    are cut, so the copy always serializes.
    """

    def __init__(self, max_characters: int, budget: int) -> None:
        self._max_characters = max_characters
        self._budget = max(0, budget)
        self._remaining = self._budget
        self._cut = False

    @property
    def used(self) -> int:
        """The characters of the budget spent so far."""
        return self._budget - self._remaining

    @property
    def remaining(self) -> int:
        """The characters of the budget left."""
        return self._remaining

    @property
    def cut(self) -> bool:
        """Whether the last :meth:`fit` or :meth:`fit_member` cut or left out anything."""
        return self._cut

    def fit(self, node: object, default: object = _OMITTED) -> tuple[object, bool]:
        """A fitted copy of ``node`` (``default`` when none of it fits), and whether it was cut."""
        self._cut = False
        fitted = self._fit(node, 0)
        if fitted is _OMITTED:
            return default, True

        return fitted, self._cut

    def fit_member(self, owner: JsonObject, key: object, value: object) -> bool:
        """Copy one member into ``owner``; False when it does not fit."""
        self._cut = False
        return self._member(owner, key, value, 0)

    def reserve(self, text: str) -> bool:
        """Spend the budget on ``text`` that is kept whole, such as a tool name or a role;
        False when it does not fit."""
        characters = max(1, len(text))
        if characters >= self._remaining:
            return False

        self._remaining -= characters
        return True

    def _member(self, owner: JsonObject, key: object, value: object, depth: int) -> bool:
        text = _key_text(key)
        # A normalized character takes at most two of the original (a rejoined pair), so a key
        # this long cannot fit; it is rejected before it is read.
        if len(text) >= 2 * self._remaining:
            self._cut = True
            return False

        name = _unique_key(owner, _normalize(text))
        if len(name) >= self._remaining:
            # Normalizing it took work in proportion to the budget left, which is spent with it,
            # so names that do not fit cannot add up to unbounded work.
            self._remaining = 0
            self._cut = True
            return False

        self._remaining -= len(name)
        fitted = self._fit(value, depth)
        if fitted is _OMITTED:
            return False

        owner[name] = fitted
        return True

    def _fit(self, node: object, depth: int) -> object:
        if isinstance(node, str):
            return self._string(node)

        if self._remaining <= 0:
            self._cut = True
            return _OMITTED

        if node is None or isinstance(node, bool):
            self._remaining -= 1
            return node

        if isinstance(node, int | float):
            if isinstance(node, float) and not math.isfinite(node):
                # NaN and the infinities are not JSON; as text the request is still sent.
                return self._string(
                    "NaN" if math.isnan(node) else ("Infinity" if node > 0 else "-Infinity")
                )

            text = _number_text(node)
            if len(text) > self._remaining:
                self._cut = True
                return _OMITTED

            self._remaining -= len(text)
            return node

        if isinstance(node, dict | list | tuple):
            if depth >= _MAX_DEPTH:
                self._cut = True
                return _OMITTED

            self._remaining -= 1
            if isinstance(node, dict):
                members: JsonObject = {}
                for key, value in node.items():
                    if not self._member(members, key, value, depth + 1):
                        break

                return members

            items: list[object] = []
            for item in node:
                fitted = self._fit(item, depth + 1)
                if fitted is _OMITTED:
                    break

                items.append(fitted)

            return items

        raise ValueError(
            f"The agent-hooks context is not JSON: a {type(node).__name__} is not serializable."
        )

    def _string(self, value: str) -> object:
        limit = min(self._max_characters, self._remaining)
        if limit <= 0:
            self._cut = True
            return _OMITTED

        # Normalized before it is measured, so a split surrogate pair counts as the one
        # character it becomes. A normalized character takes at most two of the original, so
        # this prefix decides whether the text fits, however long the original is.
        head = value[: 2 * limit + 1]
        text = _normalize(head)
        if len(head) < len(value) or len(text) > limit:
            self._cut = True
            text = _truncate(text, limit, _normalized_length(value, head, text))

        self._remaining -= max(1, len(text))
        return text


def _fit_called_tool(
    fitter: _Fitter, declared: list[object], tool_name: str, extensions: object
) -> tuple[JsonObject | None, int | None, str | None]:
    """The called tool's declaration, its index in ``declared``, and why Defender's verdict would
    not cover it, or ``None``.

    The declaration is searched for by name among the first ``_MAX_TOOL_SCAN`` entries and copied
    with its name whole, as the call's own name is. When none of the entries searched declares a
    tool, the called tool is declared from the ``a365`` extension's ``tool.description`` instead.
    Defender's verdict depends on the declaration, so it is a truncation when its description or
    schema had to be cut, or when the list is longer than the entries searched and the called
    tool is not among them; a list searched in full that does not declare the called tool is not.
    """
    called_index: int | None = None
    named = False
    for index, tool in enumerate(itertools.islice(declared, _MAX_TOOL_SCAN)):
        name = _read_string(_get(tool, "name"))
        if name == tool_name:
            called_index = index
            break

        named = named or bool(name)

    declaration: JsonObject | None = None
    cut = False
    if called_index is not None:
        declaration = {"name": _normalize(tool_name)}
        cut = _fit_tool_members(fitter, declaration, declared[called_index])
    elif not named:
        declaration = {"name": _normalize(tool_name)}
        # An extension namespace may hold any JSON value, so each level's shape is checked.
        description = _read_string(
            _get(_get(_get(extensions, _A365_EXTENSION), "tool"), "description")
        )
        if description:
            fitter.fit_member(declaration, "description", description)
            cut = fitter.cut

    if called_index is None and len(declared) > _MAX_TOOL_SCAN:
        return declaration, None, _UNSCANNED_TOOL_ERROR

    return declaration, called_index, _TRUNCATED_TOOL_ERROR if cut else None


def _fit_other_tools(
    fitter: _Fitter, declared: list[object], called_index: int | None
) -> list[object]:
    """The declarations other than the called tool's, with their spec members, in the host's
    order within what is left of the budget. Only as many entries are read as the budget could
    hold (each costs at least one character)."""
    declarations: list[object] = []
    for index, tool in enumerate(itertools.islice(declared, fitter.remaining)):
        name = _read_string(_get(tool, "name"))
        if index == called_index or not name:
            continue

        if not fitter.reserve(name):
            break

        declaration: JsonObject = {"name": _normalize(name)}
        _fit_tool_members(fitter, declaration, tool)
        declarations.append(declaration)

    return declarations


def _fit_tool_members(fitter: _Fitter, declaration: JsonObject, tool: object) -> bool:
    """Copy a tool's description (a string) and schema (an object) into ``declaration``, within
    the budget; whether either had to be cut or left out."""
    cut = False
    description = _get(tool, "description")
    if isinstance(description, str):
        fitter.fit_member(declaration, "description", description)
        cut = fitter.cut

    schema = _get(tool, "schema")
    if isinstance(schema, dict):
        fitter.fit_member(declaration, "schema", schema)
        cut = cut or fitter.cut

    return cut


def _fit_messages(fitter: _Fitter, messages: object) -> list[object]:
    """The most recent messages that fit, in their order.

    Messages are read newest first and only until the budget is spent, so a long history costs
    no more than what is sent. A message without a role or content among those read drops the
    history, since Defender rejects it.
    """
    if not isinstance(messages, list):
        return []

    fitted: list[object] = []
    for message in reversed(messages):
        role = _read_string(_get(message, "role"))
        if not isinstance(message, dict) or not role or "content" not in message:
            return []

        if not fitter.reserve(role):
            break

        prepared: JsonObject = {"role": _normalize(role)}
        if not fitter.fit_member(prepared, "content", message["content"]):
            break

        for key, value in message.items():
            if key not in ("role", "content") and not fitter.fit_member(prepared, key, value):
                break

        fitted.append(prepared)

    fitted.reverse()
    return fitted


def _content_of(node: object) -> object:
    content = _get(node, "content")
    return "" if content is None else content


def _to_arguments(args: object) -> object:
    if args is None:
        return {}

    return args if isinstance(args, dict) else {"input": args}


def _parse_verdict(payload: object) -> DefenderRtpVerdict | None:
    if not isinstance(payload, dict):
        return None

    decision = _read_string(payload.get("decision"))
    if decision not in ("allow", "deny", "transform"):
        return None

    warnings = payload.get("warnings")
    labels = payload.get("result_labels")
    return DefenderRtpVerdict(
        decision=decision,
        reason=_text(payload.get("reason")),
        message=_text(payload.get("message")),
        warnings=tuple(
            DefenderRtpWarning(_text(warning.get("reason")), _text(warning.get("message")))
            for warning in (warnings if isinstance(warnings, list) else [])
            if isinstance(warning, dict)
        ),
        result_labels=tuple(
            label for label in (labels if isinstance(labels, list) else []) if _text(label)
        ),
        transform_path=_text(_get(payload.get("transform"), "path")),
    )


def _error_detail(body: str) -> str:
    """A short single-line detail from a ProblemDetails or Defender error body.

    For a validation error (400) it is the failed rules, which Defender reports in
    ``diagnostics.validationErrors``.
    """
    try:
        payload: object = json.loads(body)
    except (ValueError, RecursionError):
        return ""

    if not isinstance(payload, dict):
        return ""

    detail = _validation_errors(payload.get("diagnostics"))
    for field in ("detail", "message", "title"):
        if detail is None:
            detail = _read_string(payload.get(field))

    detail = _WHITESPACE.sub(" ", detail or "").strip()
    if len(detail) > _MAX_ERROR_DETAIL_CHARACTERS:
        return detail[:_MAX_ERROR_DETAIL_CHARACTERS] + "..."

    return detail


def _validation_errors(diagnostics: object) -> str | None:
    parsed = diagnostics
    if isinstance(diagnostics, str):
        try:
            parsed = json.loads(diagnostics)
        except (ValueError, RecursionError):
            return None

    items = _get(parsed, "validationErrors")
    messages: list[str] = []
    for item in items if isinstance(items, list) else []:
        message = _read_string(_get(item, "message"))
        if message and message not in messages:
            messages.append(message)

    return "validation: " + "; ".join(messages) if messages else None


def _read_expiry(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims: object = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, RecursionError):
        return None

    expiry = _get(claims, "exp")
    if isinstance(expiry, bool) or not isinstance(expiry, int | float):
        return None

    try:
        seconds = float(expiry)
    except OverflowError:
        return None

    return seconds if math.isfinite(seconds) else None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value.strip())
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def _format_utc(moment: datetime) -> str:
    """An RFC 3339 UTC instant with millisecond precision."""
    return f"{moment.strftime('%Y-%m-%dT%H:%M:%S')}.{moment.microsecond // 1000:03d}Z"


def _serialize(hook: JsonObject) -> bytes:
    try:
        text = json.dumps(hook, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"The agent-hooks context is not JSON: {error}") from error

    # The fitted copy's strings are valid Unicode; "replace" only guards the encoding itself.
    return text.encode("utf-8", "replace")


def _sanitize_framework(framework: str | None) -> str:
    value = _INVALID_FRAMEWORK_CHARACTERS.sub("-", (framework or "").strip().lower()).strip("-")
    return value or _DEFAULT_FRAMEWORK


def _normalize(text: str) -> str:
    """``text`` as valid Unicode: split surrogate pairs rejoined, lone surrogates replaced.

    A lone surrogate cannot be encoded as UTF-8; left in, it would keep the request from being
    sent, and the fail mode, not Defender, would decide.
    """
    if text.isascii() or _SURROGATES.search(text) is None:
        return text

    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def _key_text(key: object) -> str:
    """The text JSON writes for a key."""
    if isinstance(key, str):
        return key

    if key is None or isinstance(key, bool):
        return "null" if key is None else ("true" if key else "false")

    if isinstance(key, int):
        return int.__repr__(key)

    if isinstance(key, float):
        return float.__repr__(key)

    raise ValueError(
        f"The agent-hooks context is not JSON: a {type(key).__name__} key is not serializable."
    )


def _unique_key(owner: JsonObject, name: str) -> str:
    """``name``, suffixed when an earlier key became equal to it (for example after a lone
    surrogate was replaced), so no member is lost."""
    if name not in owner:
        return name

    suffix = 1
    while f"{name}~{suffix}" in owner:
        suffix += 1

    return f"{name}~{suffix}"


def _number_text(number: int | float) -> str:
    """The text JSON writes for a finite number."""
    try:
        return int.__repr__(number) if isinstance(number, int) else float.__repr__(number)
    except ValueError as error:
        raise ValueError(f"The agent-hooks context is not JSON: {error}") from error


def _is_duration(value: object) -> bool:
    if isinstance(value, bool):
        return False

    if isinstance(value, int):
        return 0 <= value < 2**63

    return isinstance(value, float) and math.isfinite(value) and value >= 0


def _truncate(value: str, max_characters: int, total: int | None) -> str:
    """The beginning of a text, at most ``max_characters`` characters, ending with a truncation
    marker when one fits.

    ``value`` is the text, or its beginning when the text is longer. The marker counts the
    characters omitted from the ``total`` the whole text has, or has no count when ``total`` is
    ``None`` (not known without unbounded work).
    """
    if total is None:
        kept = max_characters - len(_UNCOUNTED_MARKER)
        return value[:max_characters] if kept <= 0 else value[:kept] + _UNCOUNTED_MARKER

    if total <= max_characters:
        return value

    omitted = total - max_characters
    while True:
        marker = f"...[truncated {omitted} chars]"
        kept = max_characters - len(marker)
        if kept <= 0:
            return value[:max_characters]

        if total - kept == omitted:
            return value[:kept] + marker

        # The marker's own length moved the cut; recount (settles within a few passes).
        omitted = total - kept


def _normalized_length(value: str, head: str, normalized_head: str) -> int | None:
    """How many characters ``value`` has once normalized, given its beginning ``head`` and that
    beginning normalized.

    ``None`` when the rest holds surrogates: only normalizing all of it would count what they
    become, and that work is not bounded (each costs the codec's error handler).
    """
    if len(head) == len(value):
        return len(normalized_head)

    if value.isascii() or _SURROGATES.search(value, len(head)) is None:
        # No surrogate in the rest: no pair spans the cut, and each of its characters stays one.
        return len(normalized_head) + len(value) - len(head)

    return None


def _is_extension_key(key: object) -> bool:
    return isinstance(key, str) and _EXTENSION_KEY.fullmatch(key) is not None


def _get(node: object, key: str) -> object:
    return node.get(key) if isinstance(node, dict) else None


def _read_string(node: object) -> str | None:
    return node if isinstance(node, str) else None


def _text(node: object) -> str | None:
    return node if isinstance(node, str) and node else None


def _is_non_negative_integer(node: object) -> bool:
    return isinstance(node, int) and not isinstance(node, bool) and node >= 0


def _first_non_empty(*values: str | None) -> str | None:
    return next((value for value in values if value is not None and value.strip()), None)


def _require_string(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{name} is required.")

    return value

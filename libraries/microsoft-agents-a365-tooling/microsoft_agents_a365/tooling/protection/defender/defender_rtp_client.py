# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Client for the Microsoft Defender for AI prevention endpoint."""

from __future__ import annotations

import asyncio
import base64
import copy
import dataclasses
import functools
import inspect
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
# Fixed-format fields the client sets itself; every other string value is clamped.
_PROTOCOL_FIELDS: Final[frozenset[str]] = frozenset({"spec", "interception_point", "timestamp"})
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

        Defender receives a fitted copy: normalized to its request validation, with every string
        value except the protocol fields clamped to
        :attr:`DefenderRtpOptions.max_content_characters`. Token acquisition and the request
        share one deadline, :attr:`DefenderRtpOptions.timeout_seconds`, so the fail mode applies
        within that time.

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
        hook = self._prepare(context, agent)
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

        return await self._post(body, point, session_id, token, started, deadline)

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

    def _prepare(self, context: Mapping[str, object], agent: DefenderRtpAgentContext) -> JsonObject:
        """A fitted copy of the context that meets Defender's request validation.

        ``target`` equals the point's field, ``tool_call`` and ``tool_result`` carry only spec
        members, the timestamp is UTC, loosely filled optional fields are repaired or dropped,
        and every string value except the protocol fields is clamped.
        """
        hook: JsonObject = copy.deepcopy(dict(context))
        hook["spec"] = self.AGENT_HOOKS_SPEC
        hook["timestamp"] = self._utc_timestamp(hook.get("timestamp"))

        agent_node = hook.get("agent")
        agent_id = _require_string(
            _first_non_empty(
                agent.agent_object_id, _read_string(_get(agent_node, "id")), agent.agent_id
            ),
            "agent.id",
        )
        session_id = _require_string(_read_string(_get(hook.get("session"), "id")), "session.id")
        sequence = hook.get("sequence")
        if isinstance(sequence, int) and _is_non_negative_integer(sequence):
            self._observe_sequence(session_id, sequence)
        else:
            hook["sequence"] = self._next_sequence(session_id)

        prepared_agent: JsonObject = {
            "id": agent_id,
            "framework": _sanitize_framework(
                _first_non_empty(_read_string(_get(agent_node, "framework")), agent.framework)
            ),
        }
        name = _first_non_empty(_read_string(_get(agent_node, "name")), agent.agent_name)
        if name is not None:
            prepared_agent["name"] = name

        version = _read_string(_get(agent_node, "version"))
        if version:
            prepared_agent["version"] = version

        hook["agent"] = prepared_agent

        # The token is issued in the agent's tenant, and Defender requires tenant.id to equal
        # the token's tid, so the agent's tenant is authoritative: a different host value would
        # only be rejected, and a rejection follows the fail mode.
        tenant = hook.get("tenant")
        prepared_tenant: JsonObject = tenant if isinstance(tenant, dict) else {}
        host_tenant_id = _read_string(prepared_tenant.get("id"))
        if host_tenant_id and host_tenant_id != agent.tenant_id:
            logger.warning(
                "Defender RTP: the context's tenant.id is not the agent's tenant; sending the "
                "agent's tenant, which the token is issued for."
            )
        prepared_tenant["id"] = agent.tenant_id
        hook["tenant"] = prepared_tenant

        if hook.get("actor") is None and agent.user_id:
            hook["actor"] = {
                "id": agent.user_id,
                "kind": agent.actor_kind if agent.actor_kind is not None else "human",
            }

        if hook.get("request_id") is None and agent.request_id:
            hook["request_id"] = agent.request_id

        if hook.get("model") is None and agent.model_name:
            hook["model"] = {"id": agent.model_name}

        _drop_invalid_optional_fields(hook)

        point = _read_string(hook.get("interception_point"))
        if point == "input":
            input_node = hook.get("input")
            role = _read_string(_get(input_node, "role"))
            content = _get(input_node, "content")
            prepared_input: JsonObject = {
                "content": "" if content is None else content,
                "role": role if role in ("system", "external") else "user",
            }
            hook["input"] = prepared_input
            hook["target"] = copy.deepcopy(prepared_input)
        elif point == "output":
            content = _get(hook.get("output"), "content")
            prepared_output: JsonObject = {"content": "" if content is None else content}
            hook["output"] = prepared_output
            hook["target"] = copy.deepcopy(prepared_output)
        elif point in ("pre_tool_call", "post_tool_call"):
            tool_call = hook.get("tool_call")
            tool_name = _require_string(_read_string(_get(tool_call, "name")), "tool_call.name")
            args = _to_arguments(_get(tool_call, "args"))
            hook["tool_call"] = {
                "id": _first_non_empty(_read_string(_get(tool_call, "id")))
                or self._generated_tool_call_id(),
                "name": tool_name,
                "args": args,
            }

            if point == "pre_tool_call":
                hook["target"] = copy.deepcopy(args)
            else:
                tool_result = hook.get("tool_result")
                value = _get(tool_result, "value")
                hook["tool_result"] = {
                    "value": value,
                    "is_error": _get(tool_result, "is_error") is True,
                }
                hook["target"] = copy.deepcopy(value)

            tools = hook.get("tools")
            if not isinstance(tools, list) or not tools:
                hook["tools"] = [_tool_from_extensions(hook, tool_name)]

        # One pass, so a clamped value is never clamped again and target still equals the
        # point's field.
        max_characters = self._options.max_content_characters
        return {
            key: value if key in _PROTOCOL_FIELDS else _clamp(value, max_characters)
            for key, value in hook.items()
        }

    # ---- transport -----------------------------------------------------------------------

    async def _post(
        self,
        body: str,
        point: str,
        session_id: str | None,
        access_token: str,
        started: float,
        deadline: float,
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
                    async with session.post(
                        endpoint, data=body.encode("utf-8"), headers=headers
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
            resolved = token_resolver(agent.agent_id, agent.tenant_id, [scope])
            token = await resolved if inspect.isawaitable(resolved) else resolved

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
        following = self._sequences.pop(session_id, 0) + 1
        self._track_sequence(session_id, following)
        return following

    def _observe_sequence(self, session_id: str, sequence: int) -> None:
        """Record a host-set sequence, so a later generated one stays above it."""
        self._track_sequence(session_id, max(self._sequences.pop(session_id, 0), sequence))

    def _track_sequence(self, session_id: str, high_water: int) -> None:
        self._sequences[session_id] = high_water
        while len(self._sequences) > _MAX_TRACKED_SESSIONS:
            del self._sequences[next(iter(self._sequences))]

    def _generated_tool_call_id(self) -> str:
        return "tooluse_" + self._id_factory().hex[:12]

    def _utc_timestamp(self, value: object) -> str:
        parsed = _parse_timestamp(value) or datetime.fromtimestamp(self._clock(), tz=UTC)
        return f"{parsed.strftime('%Y-%m-%dT%H:%M:%S')}.{parsed.microsecond // 1000:03d}Z"


def _log_failed_refresh(refresh: asyncio.Future[str]) -> None:
    if not refresh.cancelled() and refresh.exception() is not None:
        logger.warning(
            "Defender RTP token refresh failed; the cached token is used until it expires: %s",
            refresh.exception(),
        )


def _drop_invalid_optional_fields(hook: JsonObject) -> None:
    """Repair or drop optional fields a host may fill loosely but Defender validates strictly.

    A 400 would leave the call unverified: extension namespaces, ``model.id``, tool
    declarations, messages, actor.
    """
    if "extensions" in hook:
        extensions = hook["extensions"]
        if isinstance(extensions, dict):
            for key in [k for k in extensions if not _is_extension_key(k)]:
                del extensions[key]

            if not extensions:
                del hook["extensions"]
        else:
            del hook["extensions"]

    if "model" in hook:
        model_id = _read_string(_get(hook["model"], "id"))
        if model_id:
            hook["model"] = {"id": model_id}
        else:
            del hook["model"]

    if "tools" in hook:
        tools = hook["tools"]
        declarations: list[object] = []
        for tool in tools if isinstance(tools, list) else []:
            tool_name = _read_string(_get(tool, "name"))
            if not tool_name:
                continue

            declaration: JsonObject = {"name": tool_name}
            description = _read_string(_get(tool, "description"))
            if description is not None:
                declaration["description"] = description

            schema = _get(tool, "schema")
            if isinstance(schema, dict):
                declaration["schema"] = copy.deepcopy(schema)

            declarations.append(declaration)

        if declarations:
            hook["tools"] = declarations
        else:
            del hook["tools"]

    if "messages" in hook:
        messages = hook["messages"]
        valid = isinstance(messages, list) and all(
            isinstance(message, dict)
            and bool(_read_string(message.get("role")))
            and "content" in message
            for message in messages
        )
        if not valid:
            del hook["messages"]

    if "actor" in hook:
        actor = hook["actor"]
        if isinstance(actor, dict):
            prepared: JsonObject = {}
            actor_id = _read_string(actor.get("id"))
            if actor_id:
                prepared["id"] = actor_id

            kind = _read_string(actor.get("kind"))
            if kind in _ACTOR_KINDS:
                prepared["kind"] = kind

            hook["actor"] = prepared
        else:
            del hook["actor"]


def _tool_from_extensions(hook: JsonObject, tool_name: str) -> JsonObject:
    declaration: JsonObject = {"name": tool_name}
    extension = _get(hook.get("extensions"), _A365_EXTENSION)
    description = _read_string(_get(_get(extension, "tool"), "description"))
    if description:
        declaration["description"] = description

    return declaration


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


def _serialize(hook: JsonObject) -> str:
    try:
        return json.dumps(hook, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"The agent-hooks context is not JSON: {error}") from error


def _sanitize_framework(framework: str | None) -> str:
    value = _INVALID_FRAMEWORK_CHARACTERS.sub("-", (framework or "").strip().lower()).strip("-")
    return value or _DEFAULT_FRAMEWORK


def _clamp(node: object, max_characters: int) -> object:
    if node is None:
        return None

    if isinstance(node, str):
        return _truncate(node, max_characters)

    if isinstance(node, list | tuple):
        return [_clamp(item, max_characters) for item in node]

    if isinstance(node, dict):
        return {key: _clamp(value, max_characters) for key, value in node.items()}

    return copy.deepcopy(node)


def _truncate(value: str, max_characters: int) -> str:
    """At most ``max_characters`` characters, ending with a truncation marker when one fits."""
    if len(value) <= max_characters:
        return value

    omitted = len(value) - max_characters
    while True:
        marker = f"...[truncated {omitted} chars]"
        kept = max_characters - len(marker)
        if kept <= 0:
            return value[:max_characters]

        if len(value) - kept == omitted:
            return value[:kept] + marker

        # The marker's own length moved the cut; recount (settles within a few passes).
        omitted = len(value) - kept


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

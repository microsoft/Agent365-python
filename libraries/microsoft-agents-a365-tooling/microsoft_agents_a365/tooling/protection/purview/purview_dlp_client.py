# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Client for Microsoft Purview data loss prevention (DLP) through Microsoft Graph
``processContent``."""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import itertools
import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from urllib.parse import quote

import aiohttp

from ..defender._http import http_session
from .purview_dlp_agent_context import (
    PurviewDlpAgentContext,
    PurviewDlpToken,
    PurviewDlpTokenResolver,
)
from .purview_dlp_evaluation_result import (
    PurviewDlpActivity,
    PurviewDlpDecision,
    PurviewDlpEvaluationResult,
)
from .purview_dlp_options import PurviewDlpOptions

logger = logging.getLogger(__name__)

JsonObject = dict[str, object]
"""A JSON object as parsed by :mod:`json`."""

_ACTIVITIES: Final[frozenset[str]] = frozenset({"uploadText", "downloadText"})
_DEFAULT_AGENT_VERSION: Final[str] = "1.0"
_BLOCK: Final[str] = "block"
_BLOCK_ACCESS: Final[str] = "blockaccess"
# processContent's sequenceNumber is an Int64.
_MAX_SEQUENCE_NUMBER: Final[int] = 2**63 - 1
_SURROGATES = re.compile("[\ud800-\udfff]")
# Marks a member that is present with a type other than the expected one.
_MALFORMED: Final[object] = object()
_TRUNCATED_ERROR: Final[str] = (
    "content exceeded max_content_characters; Purview evaluated a truncated copy"
)
_BLOCK_REASONS: Final[dict[str, str]] = {
    "uploadText": "The request was blocked by a Microsoft Purview data loss prevention policy.",
    "downloadText": "The response was blocked by a Microsoft Purview data loss prevention policy.",
}
_FAIL_CLOSED_REASON: Final[str] = (
    "Data loss prevention validation is unavailable and this agent is configured to fail closed."
)
_TRUNCATED_FAIL_CLOSED_REASON: Final[str] = (
    "The content is too long to be fully validated by Microsoft Purview, and this agent is "
    "configured to fail closed."
)


class PurviewDlpClient:
    """Client for Microsoft Purview data loss prevention (DLP) through the Microsoft Graph
    ``processContent`` API (``POST {graph}/me/dataSecurityAndGovernance/processContent``).

    :meth:`evaluate` sends one piece of agent content (the user's message as ``uploadText``, or
    the agent's reply as ``downloadText``) for the agent's application. Purview applies the
    tenant's DLP policies scoped to that application, records the Purview audit event, and
    returns the policy actions: one whose ``restrictionAction`` is ``block`` or whose ``action``
    is ``blockAccess`` blocks the content. Each call carries a new id, sent as the
    ``client-request-id`` and as the content entry's ``identifier``.

    The protection scopes (``protectionScopes/compute``) are not computed: every content is sent,
    and Purview decides.
    """

    UPLOAD_TEXT: Final[str] = "uploadText"
    """The activity for content sent to the agent, such as the user's message."""

    DOWNLOAD_TEXT: Final[str] = "downloadText"
    """The activity for content the agent returns, such as its reply."""

    CLIENT_REQUEST_ID_HEADER: Final[str] = "client-request-id"
    """The header Microsoft Graph logs each request under."""

    def __init__(
        self,
        options: PurviewDlpOptions,
        session: aiohttp.ClientSession | None = None,
        *,
        id_factory: Callable[[], uuid.UUID] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            options: The Purview configuration, for example
                :meth:`PurviewDlpOptions.from_environment`.
            session: The HTTP session; a pooled session owned by the caller is recommended.
                When omitted, each call opens and closes its own session.
            id_factory: Creates request ids (tests).
            clock: Returns the current time in seconds since the epoch (tests).

        Raises:
            ValueError: If the options cannot be used for a client.
        """
        # A private copy: later changes to the caller's options (for example an http:// Graph
        # URL) cannot bypass the validation below.
        self._options = dataclasses.replace(options)
        self._options.validate()
        self._session = session
        self._id_factory = id_factory or uuid.uuid4
        self._clock = clock or time.time
        # Numbers the calls made without a sequence number in increasing order, so the order
        # holds within every session.
        self._sequence_numbers = itertools.count()

    @property
    def options(self) -> PurviewDlpOptions:
        """A copy of the configuration this client uses."""
        return dataclasses.replace(self._options)

    async def evaluate(
        self,
        activity: PurviewDlpActivity,
        text: str,
        agent: PurviewDlpAgentContext,
        token_resolver: PurviewDlpTokenResolver,
        *,
        session_id: str,
        sequence_number: int | None = None,
    ) -> PurviewDlpEvaluationResult | None:
        """Evaluate one piece of agent content with Purview DLP.

        Text longer than :attr:`PurviewDlpOptions.max_content_characters` is cut and sent
        flagged as truncated: Purview's block still blocks, but its allow follows the fail mode
        (``truncated``). Token acquisition and the request share one deadline,
        :attr:`PurviewDlpOptions.timeout_seconds`, so the fail mode applies within that time.

        Args:
            activity: ``uploadText`` for the user's message, ``downloadText`` for the agent's
                reply.
            text: The content.
            agent: The agent the content belongs to.
            token_resolver: Resolves the Microsoft Graph token and the user to evaluate as.
            session_id: The conversation the content belongs to, for example the agent-hooks
                ``session.id``. Sent as the entry's ``correlationId``, which groups the
                conversation's messages in Purview; required.
            sequence_number: The content's position in the conversation (for example the
                agent-hooks ``sequence``); when omitted, the client numbers its calls in
                increasing order.

        Returns:
            The result, or ``None`` when Purview DLP is disabled or the text is empty.

        Raises:
            ValueError: If the activity is unknown, the agent identity, the tenant or the
                session id is missing, or the sequence number is not an integer from 0 to
                2**63 - 1.
        """
        if not self._options.enabled:
            return None

        if activity not in _ACTIVITIES:
            raise ValueError('activity must be "uploadText" or "downloadText".')

        if not isinstance(text, str):
            raise TypeError("text must be a string.")

        if not text or text.isspace():
            return None

        if not isinstance(agent, PurviewDlpAgentContext):
            raise TypeError("agent must be a PurviewDlpAgentContext.")

        if not callable(token_resolver):
            raise TypeError("token_resolver must be callable.")

        _require_text(agent.agent_id, "agent_id")
        _require_text(agent.tenant_id, "tenant_id")
        # Without the conversation, Purview cannot group the session's messages.
        _require_text(session_id, "session_id")
        if sequence_number is not None and not _is_sequence_number(sequence_number):
            raise ValueError("sequence_number must be an integer from 0 to 2**63 - 1.")

        deadline = asyncio.get_running_loop().time() + self._options.timeout_seconds
        started = time.perf_counter()
        # One id per call: the client-request-id, and the content entry's identifier in Purview.
        correlation_id = str(self._id_factory())
        body, truncated = self._body(
            activity, text, agent, correlation_id, session_id, sequence_number
        )

        token: PurviewDlpToken | None
        try:
            async with asyncio.timeout_at(deadline):
                token = await self._resolve_token(agent, token_resolver)
        except Exception as error:
            # The exception's message can carry credentials; only its type is reported.
            logger.debug("Purview DLP token acquisition failed.", exc_info=error)
            return self._not_evaluated(
                activity,
                correlation_id,
                f"entra token unavailable ({type(error).__name__})",
                None,
                started,
            )

        if token is None:
            return self._not_evaluated(
                activity, correlation_id, "entra token unavailable", None, started
            )

        return await self._post(body, activity, token, correlation_id, started, deadline, truncated)

    def unavailable(
        self,
        activity: PurviewDlpActivity,
        error: str,
        http_status: int | None = None,
        latency_seconds: float = 0.0,
    ) -> PurviewDlpEvaluationResult:
        """A result for an evaluation that could not be made, for example without an agent
        identity.

        It follows :attr:`PurviewDlpOptions.fail_closed`, like a transport failure.

        Args:
            activity: The activity that was to be evaluated.
            error: Why no decision was obtained.
            http_status: The HTTP status, when a response was received.
            latency_seconds: Time spent before the failure, in seconds.

        Returns:
            The not-evaluated result.
        """
        return self._result_not_evaluated(
            activity, str(self._id_factory()), error, http_status, latency_seconds
        )

    # ---- request -------------------------------------------------------------------------

    def _body(
        self,
        activity: str,
        text: str,
        agent: PurviewDlpAgentContext,
        request_id: str,
        session_id: str,
        sequence_number: int | None,
    ) -> tuple[bytes, bool]:
        """The ``processContent`` request for ``text``, and whether the text was cut.

        Every string is sent as valid Unicode. The entry's ``name`` is never empty: Graph
        rejects an entry without one inline, as a processing error in an HTTP 200. Microsoft
        Graph v1.0 accepts the agent (``agents``) and ``contentCategory``.
        """
        data, truncated = _fit(text, self._options.max_content_characters)
        agent_id = _normalize(agent.agent_id)
        name = _normalize(_text(agent.agent_name) or agent.agent_id)
        version = _normalize(_text(agent.agent_version) or _DEFAULT_AGENT_VERSION)
        blueprint_id = _text(agent.blueprint_id)
        # DLP policies for an agent are scoped to its blueprint's application.
        application_id = _normalize(_text(agent.application_id) or blueprint_id or agent.agent_id)
        conversation_id = _normalize(session_id)
        sequence = sequence_number if sequence_number is not None else next(self._sequence_numbers)
        timestamp = _format_utc(datetime.fromtimestamp(self._clock(), tz=UTC))
        described: JsonObject = {
            "@odata.type": "microsoft.graph.aiAgentInfo",
            "identifier": agent_id,
            "name": name,
            "version": version,
        }
        if blueprint_id is not None:
            described["blueprintId"] = _normalize(blueprint_id)

        body: JsonObject = {
            "contentToProcess": {
                "contentEntries": [
                    {
                        "@odata.type": "microsoft.graph.processConversationMetadata",
                        "identifier": request_id,
                        "content": {
                            "@odata.type": "microsoft.graph.textContent",
                            "data": data,
                        },
                        "name": f"{name} {activity}",
                        "correlationId": conversation_id,
                        "sequenceNumber": sequence,
                        "isTruncated": truncated,
                        "createdDateTime": timestamp,
                        "modifiedDateTime": timestamp,
                        "contentCategory": "ai",
                        "agents": [described],
                    }
                ],
                "activityMetadata": {"activity": activity},
                "integratedAppMetadata": {"name": name, "version": version},
                "protectedAppMetadata": {
                    "name": name,
                    "version": version,
                    "applicationLocation": {
                        "@odata.type": "microsoft.graph.policyLocationApplication",
                        "value": application_id,
                    },
                },
            }
        }
        text_body = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        # Every string is valid Unicode; "replace" only guards the encoding itself.
        return text_body.encode("utf-8", "replace"), truncated

    # ---- transport -----------------------------------------------------------------------

    async def _post(
        self,
        body: bytes,
        activity: str,
        token: PurviewDlpToken,
        correlation_id: str,
        started: float,
        deadline: float,
        truncated: bool,
    ) -> PurviewDlpEvaluationResult:
        principal = "/me" if token.user_id is None else f"/users/{quote(token.user_id, safe='')}"
        url = (
            f"{self._options.graph_base_url.rstrip('/')}{principal}"
            "/dataSecurityAndGovernance/processContent"
        )
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
            self.CLIENT_REQUEST_ID_HEADER: correlation_id,
        }
        status: int | None = None
        raw: bytes | None = None
        error: str | None = None
        try:
            async with asyncio.timeout_at(deadline):
                async with http_session(self._session) as session:
                    # No redirects: a 307/308 would resend the content and the token to a target
                    # that never passed the HTTPS check; a 3xx follows the fail mode.
                    async with session.post(
                        url, data=body, headers=headers, allow_redirects=False
                    ) as response:
                        status = response.status
                        try:
                            raw = await response.read()
                        except TimeoutError:
                            raise
                        except Exception as read_error:
                            error = f"response body could not be read ({type(read_error).__name__})"
        except TimeoutError:
            error = "request timeout"
        except Exception as send_error:
            # Any failure that is not the caller's cancellation (for example from a retry or
            # circuit-breaker session) is not a decision: it follows the fail mode.
            error = f"request failed ({type(send_error).__name__})"

        if error is not None or status is None or raw is None:
            return self._not_evaluated(
                activity, correlation_id, error or "request failed", status, started
            )

        decision: PurviewDlpDecision
        state: str | None = None
        if status in (202, 204):
            # Accepted without an inline decision: Purview applied no policy action.
            decision = PurviewDlpDecision()
        elif not 200 <= status < 300:
            return self._not_evaluated(activity, correlation_id, f"http {status}", status, started)
        else:
            try:
                payload: object = json.loads(raw)
            except (ValueError, RecursionError):
                return self._not_evaluated(
                    activity, correlation_id, "non-JSON response", status, started
                )

            parsed = _parse_response(payload)
            if isinstance(parsed, str):
                return self._not_evaluated(activity, correlation_id, parsed, status, started)

            decision, state = parsed

        latency = time.perf_counter() - started
        if truncated and not decision.block_action:
            # Purview evaluated a truncated copy; its allow does not cover what was cut, which
            # the agent would still act on. A block stays authoritative.
            fail_closed = self._options.fail_closed
            logger.warning(
                "Purview DLP %s: %s (%s), client-request-id=%s",
                activity,
                _TRUNCATED_ERROR,
                "blocked" if fail_closed else "allowed",
                correlation_id,
            )
            return PurviewDlpEvaluationResult(
                allowed=not fail_closed,
                evaluated=True,
                activity=activity,
                correlation_id=correlation_id,
                decision=decision,
                truncated=True,
                protection_scope_state=state,
                http_status=status,
                latency_seconds=latency,
                error=_TRUNCATED_ERROR,
                block_reason=_TRUNCATED_FAIL_CLOSED_REASON if fail_closed else None,
            )

        logger.debug(
            "Purview DLP %s: block=%s actions=%d client-request-id=%s",
            activity,
            decision.block_action,
            decision.action_count,
            correlation_id,
        )
        return PurviewDlpEvaluationResult(
            allowed=not decision.block_action,
            evaluated=True,
            activity=activity,
            correlation_id=correlation_id,
            decision=decision,
            truncated=truncated,
            protection_scope_state=state,
            http_status=status,
            latency_seconds=latency,
            block_reason=_BLOCK_REASONS[activity] if decision.block_action else None,
        )

    def _not_evaluated(
        self,
        activity: str,
        correlation_id: str,
        error: str,
        http_status: int | None,
        started: float,
    ) -> PurviewDlpEvaluationResult:
        return self._result_not_evaluated(
            activity, correlation_id, error, http_status, time.perf_counter() - started
        )

    def _result_not_evaluated(
        self,
        activity: str,
        correlation_id: str,
        error: str,
        http_status: int | None,
        latency_seconds: float,
    ) -> PurviewDlpEvaluationResult:
        fail_closed = self._options.fail_closed
        logger.warning(
            "Purview DLP %s was not evaluated (%s), client-request-id=%s: %s",
            activity,
            "blocked" if fail_closed else "allowed",
            correlation_id,
            error,
        )
        return PurviewDlpEvaluationResult(
            allowed=not fail_closed,
            evaluated=False,
            activity=activity,
            correlation_id=correlation_id,
            http_status=http_status,
            latency_seconds=latency_seconds,
            error=error,
            block_reason=_FAIL_CLOSED_REASON if fail_closed else None,
        )

    # ---- authentication ------------------------------------------------------------------

    async def _resolve_token(
        self, agent: PurviewDlpAgentContext, token_resolver: PurviewDlpTokenResolver
    ) -> PurviewDlpToken | None:
        """The token from ``token_resolver``, which may be sync or async.

        A synchronous resolver (for example one that calls MSAL directly) would block the event
        loop, where the deadline cannot interrupt it, so it runs on a worker thread. Calls are
        not shared: a delegated token is per user, and a resolver may depend on the call's
        context (for example the signed-in user), so each call resolves its own.
        """
        scopes = [self._options.authentication_scope]
        resolved: object
        if inspect.iscoroutinefunction(token_resolver):
            resolved = token_resolver(agent, scopes)
        else:
            resolved = await asyncio.to_thread(token_resolver, agent, scopes)

        token = await resolved if inspect.isawaitable(resolved) else resolved
        if (
            not isinstance(token, PurviewDlpToken)
            or not isinstance(token.access_token, str)
            or not token.access_token.strip()
        ):
            return None

        user_id = token.user_id
        if user_id is not None and (not isinstance(user_id, str) or not user_id.strip()):
            raise ValueError("The Purview token resolver returned an empty user id.")

        return token


def _parse_response(payload: object) -> tuple[PurviewDlpDecision, str | None] | str:
    """The decision and protection scope state in a ``processContent`` response, or why the
    response holds no decision.

    Every node is shape-checked. A policy action blocks when its ``restrictionAction`` is
    ``block`` or its ``action`` is ``blockAccess`` (any case), as in Microsoft's own Purview
    integrations; a block stands even beside processing errors or malformed actions. Otherwise
    processing errors (Graph reports a request it rejected, such as an entry without a name,
    inline in an HTTP 200), or a response without a well-formed list of policy actions, mean the
    content was not evaluated.
    """
    if not isinstance(payload, dict):
        return "response was not a JSON object"

    actions = payload.get("policyActions")
    listed = isinstance(actions, list)
    malformed = not listed
    blocks = False
    blocking: str | None = None
    first: str | None = None
    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, dict):
            malformed = True
            continue

        restriction = _optional_string(action.get("restrictionAction"))
        kind = _optional_string(action.get("action"))
        if restriction is _MALFORMED or kind is _MALFORMED:
            malformed = True

        restriction_text = restriction if isinstance(restriction, str) else None
        kind_text = kind if isinstance(kind, str) else None
        if restriction_text and first is None:
            first = restriction_text

        if (restriction_text is not None and restriction_text.lower() == _BLOCK) or (
            kind_text is not None and kind_text.lower() == _BLOCK_ACCESS
        ):
            blocks = True
            if blocking is None and restriction_text:
                blocking = restriction_text

    state = payload.get("protectionScopeState")
    decision = PurviewDlpDecision(
        block_action=blocks,
        restriction_action=blocking if blocks else first,
        action_count=len(actions) if isinstance(actions, list) else 0,
    )
    protection_scope_state = state if isinstance(state, str) and state else None
    if blocks:
        return decision, protection_scope_state

    errors = payload.get("processingErrors")
    if errors is not None and not isinstance(errors, list):
        return "response had processingErrors that are not a list"

    if errors:
        return f"processing errors: {len(errors)}"

    if malformed:
        return (
            "response had a policy action of another shape"
            if listed
            else "response had no list of policy actions"
        )

    return decision, protection_scope_state


def _optional_string(value: object) -> str | object | None:
    """A string member; ``None`` when it is absent, and ``_MALFORMED`` when it has another type."""
    if value is None:
        return None

    return value if isinstance(value, str) else _MALFORMED


def _fit(text: str, max_characters: int) -> tuple[str, bool]:
    """``text`` as valid Unicode, cut to ``max_characters`` characters, and whether it was cut.

    Only the first ``2 * max_characters + 1`` characters are read: a normalized character takes
    at most two of the original (a rejoined surrogate pair), so this prefix decides whether the
    text fits, however long it is.
    """
    head = text[: 2 * max_characters + 1]
    normalized = _normalize(head)
    if len(head) < len(text) or len(normalized) > max_characters:
        return normalized[:max_characters], True

    return normalized, False


def _normalize(text: str) -> str:
    """``text`` as valid Unicode: split surrogate pairs rejoined, lone surrogates replaced.

    A lone surrogate cannot be encoded as UTF-8; left in, it would keep the request from being
    sent, and the fail mode, not Purview, would decide.
    """
    if text.isascii() or _SURROGATES.search(text) is None:
        return text

    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def _format_utc(moment: datetime) -> str:
    """An ISO 8601 UTC instant with millisecond precision."""
    return f"{moment.strftime('%Y-%m-%dT%H:%M:%S')}.{moment.microsecond // 1000:03d}Z"


def _is_sequence_number(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_SEQUENCE_NUMBER
    )


def _text(value: object) -> str | None:
    """``value`` when it is a string that is not blank."""
    return value if isinstance(value, str) and value.strip() else None


def _require_text(value: object, name: str) -> str:
    text = _text(value)
    if text is None:
        raise ValueError(f"{name} is required.")

    return text

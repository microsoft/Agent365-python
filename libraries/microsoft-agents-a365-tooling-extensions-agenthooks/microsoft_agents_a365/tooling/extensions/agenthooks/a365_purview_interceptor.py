# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Purview data loss prevention (DLP) as an agent-hooks interceptor."""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import inspect
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

from agent_hooks import AgentContext, Decision, Evidence, Verdict
from agent_hooks import Warning as HookWarning
from microsoft_agents_a365.tooling.protection.purview import (
    PurviewDlpActivity,
    PurviewDlpAgentContext,
    PurviewDlpClient,
    PurviewDlpEvaluationResult,
    PurviewDlpTokenResolver,
)

logger = logging.getLogger(__name__)

_BLOCK_MESSAGES: Final[dict[str, str]] = {
    "uploadText": "The request was blocked by a Microsoft Purview data loss prevention policy.",
    "downloadText": "The response was blocked by a Microsoft Purview data loss prevention policy.",
}
_FAIL_CLOSED_MESSAGE: Final[str] = (
    "Data loss prevention validation is unavailable and this agent is configured to fail closed."
)
_TRUNCATED_BLOCK_MESSAGE: Final[str] = (
    "The content is too long to be fully validated by Microsoft Purview, and this agent is "
    "configured to fail closed."
)
_NO_IDENTITY_ERROR: Final[str] = "no agent identity was resolved"
# A reply audit is bounded by the client's timeout plus this margin, so the client's own
# deadline applies first and the result keeps the request's correlation id.
_AUDIT_MARGIN_SECONDS: Final[float] = 2.0
_MAX_SEQUENCE_NUMBER: Final[int] = 2**63 - 1


@dataclass(frozen=True)
class A365PurviewCall:
    """The agent and credentials for the Purview call of one emitted context.

    Attributes:
        agent: The agent the content belongs to. When it has no ``agent_name``, the context's
            ``agent.name`` names it.
        token_resolver: Resolves the Microsoft Graph token and the user to evaluate as, for
            example :meth:`PurviewDlpTokenResolvers.from_agentic_user`.
    """

    agent: PurviewDlpAgentContext
    token_resolver: PurviewDlpTokenResolver


A365PurviewCallResolver = Callable[
    [AgentContext], A365PurviewCall | None | Awaitable[A365PurviewCall | None]
]
"""Returns the agent and token resolver for an emitted context; may be async."""


class A365PurviewInterceptor:
    """An agent-hooks interceptor for Microsoft Purview data loss prevention (DLP).

    At ``input``, the user's message is evaluated as ``uploadText`` and Purview's decision
    decides: a policy action that blocks denies the context. At ``output``, the agent's reply is
    evaluated as ``downloadText``: in the ``audit`` response mode (the default) it is sent to
    Purview in the background and the reply is allowed at once, since Purview DLP policies for AI
    apps restrict prompts, not replies; in ``enforce`` it is awaited and mapped like the input.
    Other points are allowed without a call, as is content without text. Structured content (for
    example content parts) is sent as its string and number values, one per line.

    When no decision is obtained (transport, authentication or processing failure, no agent
    identity resolved, or an error from the call resolver or the token resolver), the verdict
    follows :attr:`PurviewDlpOptions.fail_closed`: allow with a ``purview:unverified`` warning,
    or deny with reason ``runtime_error:purview_unverified``, which is never reported as a
    detection. A reply audit never holds or blocks the reply; its outcome is only reported.
    """

    NAME: Final[str] = "purview"
    """The name the interceptor is registered under."""

    def __init__(
        self,
        client: PurviewDlpClient,
        resolve_call: A365PurviewCallResolver,
        on_evaluated: Callable[[PurviewDlpEvaluationResult], None] | None = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            client: The Purview client.
            resolve_call: Returns the agent and token resolver for a context, for example from
                the current turn. It is called only for content with text at ``input`` and
                ``output`` while Purview DLP is enabled. ``None`` (no agent identity, for example
                an activity without an agentic user) follows the fail mode, like an unavailable
                Purview.
            on_evaluated: Receives each evaluation, including reply audits, for logging and
                telemetry (for example the correlation id). It runs on a worker thread once the
                verdict is decided, outside the emitter's interceptor timeout, so neither an
                exception it raises (which is logged) nor the time it takes changes the verdict;
                callbacks for concurrent evaluations may run concurrently.
        """
        if client is None:
            raise TypeError("client is required.")

        if resolve_call is None:
            raise TypeError("resolve_call is required.")

        self._client = client
        self._resolve_call = resolve_call
        self._on_evaluated = on_evaluated
        # The event loop keeps only weak references to tasks; these keep the reply audits
        # running until they complete.
        self._audits: set[asyncio.Task[None]] = set()

    async def intercept(self, context: AgentContext, /) -> Verdict:
        """Evaluate one emitted context with Purview.

        Args:
            context: The agent-hooks context the emitter dispatches.

        Returns:
            The agent-hooks verdict for the context.
        """
        options = self._client.options
        point = context.get("interception_point")
        if not options.enabled or point not in ("input", "output"):
            return Verdict.allow()

        if point == "output" and options.response_mode == "audit":
            self._start_audit(context, options.timeout_seconds)
            return Verdict.allow()

        result = await self._evaluate(
            PurviewDlpClient.UPLOAD_TEXT if point == "input" else PurviewDlpClient.DOWNLOAD_TEXT,
            context,
        )
        if result is None:
            return Verdict.allow()

        # The verdict is decided before the callback sees the result, and the callback runs on a
        # worker thread, off the emitter's timed interception, so neither what it does nor how
        # long it takes changes the verdict.
        verdict = self.to_verdict(result)
        self._notify(result)
        return verdict

    async def wait_for_pending_audits(self) -> None:
        """Wait until the reply audits started so far complete, for example before shutdown.

        Each audit is bounded by the client's timeout; their outcomes go to ``on_evaluated``.
        """
        pending = set(self._audits)
        if pending:
            await asyncio.wait(pending)

    @staticmethod
    def to_verdict(result: PurviewDlpEvaluationResult) -> Verdict:
        """Map a Purview evaluation to the agent-hooks verdict the host composes.

        Args:
            result: The Purview evaluation.

        Returns:
            The agent-hooks verdict.
        """
        name = A365PurviewInterceptor.NAME
        if result.verified:
            if result.allowed:
                return Verdict.allow()

            return Verdict(
                decision=Decision.DENY,
                reason=f"{name}:block",
                message=result.block_reason
                or _BLOCK_MESSAGES.get(result.activity, _BLOCK_MESSAGES["uploadText"]),
                evidence=Evidence(
                    artefact=f"{name}-verdict",
                    verification_pointers={
                        "correlation": f"urn:a365:{name}:{quote(result.correlation_id, safe='')}"
                    },
                ),
            )

        # No decision, or an allow of a truncated copy that does not cover the whole content.
        unverified = (
            HookWarning(
                reason=f"{name}:unverified", message=result.error or "no verdict was returned"
            ),
        )
        if result.allowed:
            return Verdict(decision=Decision.ALLOW, warnings=unverified)

        return Verdict(
            decision=Decision.DENY,
            reason=f"runtime_error:{name}_unverified",
            message=result.block_reason
            or (_TRUNCATED_BLOCK_MESSAGE if result.truncated else _FAIL_CLOSED_MESSAGE),
            warnings=unverified,
        )

    async def _evaluate(
        self, activity: PurviewDlpActivity, context: AgentContext
    ) -> PurviewDlpEvaluationResult | None:
        """Evaluate the context's content; ``None`` when it has no text or Purview is disabled.

        A failure to read the content, to resolve the identity or to evaluate is never a
        decision: it follows the fail mode. Only the exception's type reaches the result, and so
        the verdict and the interception record, since its message can carry credentials or
        content; the exception itself goes to the log.
        """
        limit = self._client.options.max_content_characters
        try:
            # A normalized character takes at most two of the original (a rejoined surrogate
            # pair), so reading past twice the limit always leaves the client more than the
            # limit to cut and flag as truncated.
            text, complete = _content_text(_content_of(context, activity), 2 * limit)
        except Exception as error:
            logger.warning(
                "The %s content could not be read; the fail mode applies.",
                activity,
                exc_info=error,
            )
            return self._client.unavailable(
                activity, f"content could not be read ({type(error).__name__})"
            )

        if not text or text.isspace():
            # Nothing to evaluate, so no identity is needed. Content whose first characters are
            # blank but that goes on past the limit is not empty: the rest was never read, so it
            # follows the fail mode.
            return (
                None
                if complete
                else self._client.unavailable(
                    activity,
                    f"content exceeded max_content_characters ({limit}) before any text; "
                    "Purview was not called",
                )
            )

        try:
            resolved = self._resolve_call(context)
            call = await resolved if inspect.isawaitable(resolved) else resolved
            if call is None:
                # No agent identity means no decision can be obtained, never an allow.
                return self._client.unavailable(activity, _NO_IDENTITY_ERROR)

            agent = call.agent
            if isinstance(agent, PurviewDlpAgentContext) and not _text(agent.agent_name):
                agent = dataclasses.replace(agent, agent_name=_agent_name(context))

            return await self._client.evaluate(
                activity,
                text,
                agent,
                call.token_resolver,
                session_id=_session_id(context),
                sequence_number=_sequence_number(context),
            )
        except Exception as error:
            logger.warning(
                "The Purview evaluation failed for %s; the fail mode applies.",
                activity,
                exc_info=error,
            )
            return self._client.unavailable(activity, f"evaluation failed ({type(error).__name__})")

    def _start_audit(self, context: AgentContext, timeout_seconds: float) -> None:
        """Send the reply to Purview in the background; the reply is not held."""
        task = asyncio.get_running_loop().create_task(self._audit(context, timeout_seconds))
        self._audits.add(task)
        task.add_done_callback(self._audit_done)

    async def _audit(self, context: AgentContext, timeout_seconds: float) -> None:
        activity: PurviewDlpActivity = "downloadText"
        # Its own task: the emitter's timeout and cancellation of the interception do not reach
        # it, and its own bound keeps it from outliving the client's timeout by much.
        try:
            async with asyncio.timeout(timeout_seconds + _AUDIT_MARGIN_SECONDS):
                result = await self._evaluate(activity, context)
        except TimeoutError:
            result = self._client.unavailable(activity, "evaluation timeout")

        if result is not None:
            logger.debug(
                "Purview reply audit: evaluated=%s block=%s actions=%d client-request-id=%s",
                result.evaluated,
                result.decision.block_action,
                result.decision.action_count,
                result.correlation_id,
            )
            self._notify(result)

    def _audit_done(self, task: asyncio.Task[None]) -> None:
        self._audits.discard(task)
        # Retrieve the failure so it is contained and logged, not reported as never retrieved.
        if not task.cancelled() and task.exception() is not None:
            logger.error("The Purview reply audit failed.", exc_info=task.exception())

    def _notify(self, result: PurviewDlpEvaluationResult) -> None:
        if self._on_evaluated is None:
            return

        try:
            asyncio.get_running_loop().run_in_executor(
                None,
                contextvars.copy_context().run,
                _notify_evaluated,
                self._on_evaluated,
                result,
            )
        except Exception:
            logger.exception("The Purview evaluation callback could not be scheduled.")


def _content_of(context: AgentContext, activity: PurviewDlpActivity) -> object:
    """The content of the context's ``input`` (``uploadText``) or ``output`` (``downloadText``)."""
    node = context.get("input" if activity == "uploadText" else "output")
    return node.get("content") if isinstance(node, dict) else None


def _content_text(content: object, budget: int) -> tuple[str, bool]:
    """The text of a message's content, and whether all of it was read.

    A string is the text as it is. Structured content (for example content parts) gives its
    string and number values in order, one per line, each container read once. At most
    ``budget`` characters plus one are kept, the last one only to mark the text as longer than
    the budget: the client sends only the beginning and flags the rest as truncated, so the
    work stays bounded however long a value is. A value cut to fit means not all was read.
    """
    if isinstance(content, str):
        return content, True

    parts: list[str] = []
    # The length of the joined text, separators included; never more than budget + 1.
    length = 0
    pending: list[object] = [content]
    seen: set[int] = set()
    while pending and length <= budget:
        node = pending.pop()
        if isinstance(node, dict | list | tuple):
            if id(node) not in seen:
                seen.add(id(node))
                children = list(node.values() if isinstance(node, dict) else node)
                children.reverse()
                pending.extend(children)

            continue

        text = _value_text(node)
        if not text:
            continue

        separator = 1 if parts else 0
        room = budget + 1 - length - separator
        if len(text) > room:
            parts.append(text[:room])
            return "\n".join(parts), False

        length += separator + len(text)
        parts.append(text)

    return "\n".join(parts), not pending


def _value_text(value: object) -> str:
    """The text of a string or finite number; nothing for other values."""
    if isinstance(value, str):
        return value

    if isinstance(value, bool):
        return ""

    if isinstance(value, int):
        return int.__repr__(value)

    if isinstance(value, float) and math.isfinite(value):
        return float.__repr__(value)

    return ""


def _session_id(context: AgentContext) -> str | None:
    session = context.get("session")
    return _text(session.get("id") if isinstance(session, dict) else None)


def _agent_name(context: AgentContext) -> str | None:
    agent = context.get("agent")
    return _text(agent.get("name") if isinstance(agent, dict) else None)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _sequence_number(context: AgentContext) -> int | None:
    sequence = context.get("sequence")
    if (
        isinstance(sequence, int)
        and not isinstance(sequence, bool)
        and 0 <= sequence <= _MAX_SEQUENCE_NUMBER
    ):
        return sequence

    return None


def _notify_evaluated(
    on_evaluated: Callable[[PurviewDlpEvaluationResult], None],
    result: PurviewDlpEvaluationResult,
) -> None:
    """Hand an evaluation to the host's callback. It is for logging and telemetry, so its
    failure is logged and never changes the verdict."""
    try:
        on_evaluated(result)
    except Exception:
        logger.exception(
            "The Purview evaluation callback failed for %s; the verdict is unchanged. "
            "client-request-id=%s",
            result.activity,
            result.correlation_id,
        )

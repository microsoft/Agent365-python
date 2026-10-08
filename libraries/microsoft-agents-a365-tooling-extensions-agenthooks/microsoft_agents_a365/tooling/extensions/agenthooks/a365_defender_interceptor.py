# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Defender for AI real-time protection as an agent-hooks interceptor."""

from __future__ import annotations

import inspect
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

from agent_hooks import AgentContext, Decision, Evidence, Verdict
from agent_hooks import Warning as HookWarning
from microsoft_agents_a365.tooling.protection.defender import (
    DefenderRtpAgentContext,
    DefenderRtpClient,
    DefenderRtpEvaluationResult,
    DefenderRtpTokenResolver,
)

logger = logging.getLogger(__name__)

_INVALID_REASON_CHARACTERS = re.compile(r"[^A-Za-z0-9_.-]")
_FAIL_CLOSED_MESSAGE: Final[str] = (
    "Security validation is unavailable and this agent is configured to fail closed."
)


@dataclass(frozen=True)
class A365DefenderCall:
    """The agent identity and credentials for the Defender call of one emitted context.

    Attributes:
        agent: The agent identity and turn; fills context fields the host did not set.
        token_resolver: Resolves the agent identity's Defender token, for example
            :meth:`DefenderRtpTokenResolvers.from_agentic_connection`.
    """

    agent: DefenderRtpAgentContext
    token_resolver: DefenderRtpTokenResolver


A365DefenderCallResolver = Callable[
    [AgentContext], A365DefenderCall | None | Awaitable[A365DefenderCall | None]
]
"""Returns the agent identity and token resolver for an emitted context; may be async."""


class A365DefenderInterceptor:
    """An agent-hooks interceptor for Microsoft Defender for AI real-time protection.

    For each context the host emits at ``input``, ``pre_tool_call``, ``post_tool_call`` or
    ``output``, Defender receives a fitted copy (normalized to its request validation and
    clamped, keeping the context's session, sequence and tool call ids), and Defender's verdict
    decides: ``deny`` blocks the action. Other points are allowed without a call.

    When no verdict is obtained (transport, authentication or validation failure), the verdict
    follows :attr:`DefenderRtpOptions.fail_closed`: allow with a ``defender:unverified``
    warning, or deny with reason ``runtime_error:defender_unverified``, which is never reported
    as a detection.
    """

    NAME: Final[str] = "defender"
    """The name the interceptor is registered under."""

    def __init__(
        self,
        client: DefenderRtpClient,
        resolve_call: A365DefenderCallResolver,
        on_evaluated: Callable[[DefenderRtpEvaluationResult], None] | None = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            client: The Defender client.
            resolve_call: Returns the agent identity and token resolver for a context, for
                example from the current turn; ``None`` allows the context without a call.
            on_evaluated: Receives each evaluation, for logging and telemetry (for example the
                correlation id). An exception it raises is logged and does not change the
                verdict.
        """
        if client is None:
            raise TypeError("client is required.")

        if resolve_call is None:
            raise TypeError("resolve_call is required.")

        self._client = client
        self._resolve_call = resolve_call
        self._on_evaluated = on_evaluated

    async def intercept(self, context: AgentContext, /) -> Verdict:
        """Evaluate one emitted context with Defender.

        Args:
            context: The agent-hooks context the emitter dispatches.

        Returns:
            The agent-hooks verdict for the context.
        """
        resolved = self._resolve_call(context)
        call = await resolved if inspect.isawaitable(resolved) else resolved
        if call is None:
            return Verdict.allow()

        result: DefenderRtpEvaluationResult | None
        try:
            result = await self._client.evaluate_hook_context(
                context, call.agent, call.token_resolver
            )
        except Exception as error:
            # An invalid context or identity is never a verdict: it follows the fail mode.
            point = context.get("interception_point")
            result = self._client.unavailable(
                point if isinstance(point, str) else "", f"{type(error).__name__}: {error}"
            )

        if result is None:
            return Verdict.allow()

        if self._on_evaluated is not None:
            try:
                self._on_evaluated(result)
            except Exception:
                logger.exception("The Defender on_evaluated callback failed.")

        return self.to_verdict(result)

    @staticmethod
    def to_verdict(result: DefenderRtpEvaluationResult) -> Verdict:
        """Map a Defender evaluation to the agent-hooks verdict the host composes.

        Args:
            result: The Defender evaluation.

        Returns:
            The agent-hooks verdict.
        """
        name = A365DefenderInterceptor.NAME
        if result.evaluated:
            verdict = result.verdict
            labels = verdict.result_labels if verdict is not None else ()
            if result.allowed:
                warnings = tuple(
                    HookWarning(
                        reason=warning.reason or f"{name}:warning",
                        message=warning.message or "",
                    )
                    for warning in (verdict.warnings if verdict is not None else ())
                )
                return Verdict(decision=Decision.ALLOW, warnings=warnings, result_labels=labels)

            reason = verdict.reason if verdict is not None else None
            code = ":" + _INVALID_REASON_CHARACTERS.sub("_", reason) if reason else ""
            return Verdict(
                decision=Decision.DENY,
                reason=f"{name}:block{code}",
                message=result.block_reason,
                evidence=Evidence(
                    artefact=f"{name}-verdict",
                    verification_pointers={
                        "correlation": f"urn:a365:{name}:{quote(result.correlation_id, safe='')}"
                    },
                ),
                result_labels=labels,
            )

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
            message=result.block_reason or _FAIL_CLOSED_MESSAGE,
            warnings=unverified,
        )

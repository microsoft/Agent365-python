# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""The outcome of a Purview evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PurviewDlpActivity = Literal["uploadText", "downloadText"]
"""The Purview activity evaluated: ``uploadText`` for content sent to the agent (the user's
message), ``downloadText`` for content the agent returns (its reply)."""


@dataclass(frozen=True)
class PurviewDlpDecision:
    """The policy actions Purview returned.

    Attributes:
        block_action: Whether a policy action blocks the content: its ``restrictionAction`` is
            ``block`` or its ``action`` is ``blockAccess`` (any case).
        restriction_action: The ``restrictionAction`` of the blocking action, when it has one;
            when nothing blocks, of the first action that has one (for example ``warn`` or
            ``audit``).
        action_count: How many policy actions Purview returned, blocking or not.
    """

    block_action: bool = False
    restriction_action: str | None = None
    action_count: int = 0


@dataclass(frozen=True)
class PurviewDlpEvaluationResult:
    """The outcome of one Purview evaluation.

    ``evaluated`` is false when no decision was obtained; ``allowed`` then follows
    :attr:`PurviewDlpOptions.fail_closed`. ``truncated`` is true when Purview evaluated content
    cut to :attr:`PurviewDlpOptions.max_content_characters`: a block still blocks, but an allow
    does not cover what was cut, so ``allowed`` then follows the fail mode too.

    Attributes:
        allowed: Whether the content may proceed.
        evaluated: Whether Purview returned a decision.
        activity: The activity evaluated, ``uploadText`` or ``downloadText``.
        correlation_id: The ``client-request-id`` sent with the call, which is also the content
            entry's ``identifier``; Microsoft Graph logs the request under it.
        decision: The policy actions Purview returned.
        truncated: Whether Purview evaluated content cut to the limit.
        protection_scope_state: Purview's ``protectionScopeState``, when returned.
        http_status: The HTTP status, when a response was received.
        latency_seconds: Time spent on the evaluation, in seconds.
        error: Why no decision was obtained, or why an allow is not authoritative, for example
            ``http 403``. Carries at most an exception's type, never a response body or token.
        block_reason: A user-facing reason when the content is blocked.
    """

    allowed: bool
    evaluated: bool
    activity: str = ""
    correlation_id: str = ""
    decision: PurviewDlpDecision = field(default_factory=PurviewDlpDecision)
    truncated: bool = False
    protection_scope_state: str | None = None
    http_status: int | None = None
    latency_seconds: float = 0.0
    error: str | None = None
    block_reason: str | None = None

    @property
    def verified(self) -> bool:
        """Whether Purview's decision decides the content.

        False when no decision was obtained, or when Purview allowed content cut to the limit;
        the result then follows the fail mode.
        """
        if not self.evaluated:
            return False

        return self.decision.block_action or not self.truncated

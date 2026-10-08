# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""The outcome of a Defender evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefenderRtpWarning:
    """A warning attached to a Defender verdict.

    Attributes:
        reason: Machine-readable reason, for example ``prevention_annotated``.
        message: Human-readable message.
    """

    reason: str | None
    message: str | None


@dataclass(frozen=True)
class DefenderRtpVerdict:
    """The agent-hooks verdict returned by the Defender prevention endpoint.

    Attributes:
        decision: ``allow``, ``deny``, or ``transform``.
        reason: Defender's reason, for example ``prevention_blocked``.
        message: Defender's message for the block.
        warnings: Warnings, for example an annotation or a point that is not evaluated.
        result_labels: Threat labels, for example ``PromptInjection``.
        transform_path: For ``transform``: the JSON pointer of the content to rewrite.
    """

    decision: str = "allow"
    reason: str | None = None
    message: str | None = None
    warnings: tuple[DefenderRtpWarning, ...] = ()
    result_labels: tuple[str, ...] = ()
    transform_path: str | None = None


@dataclass(frozen=True)
class DefenderRtpEvaluationResult:
    """The outcome of one Defender evaluation.

    ``evaluated`` is false when no verdict was obtained; ``allowed`` then follows
    :attr:`DefenderRtpOptions.fail_closed`.

    Attributes:
        allowed: Whether the action may proceed.
        evaluated: Whether Defender returned a verdict.
        interception_point: The agent-hooks interception point that was evaluated.
        correlation_id: The ``x-ms-correlation-id`` sent with the call; Defender logs the
            evaluation under it.
        session_id: The agent-hooks ``session.id``.
        verdict: Defender's verdict, when one was returned.
        http_status: The HTTP status, when a response was received.
        error: Why no verdict was obtained, for example ``http 403: ...``.
        latency_seconds: Time spent on the evaluation call, in seconds.
        block_reason: A user-facing reason when the action is blocked.
    """

    allowed: bool
    evaluated: bool
    interception_point: str = ""
    correlation_id: str = ""
    session_id: str | None = None
    verdict: DefenderRtpVerdict | None = None
    http_status: int | None = None
    error: str | None = None
    latency_seconds: float = 0.0
    block_reason: str | None = None

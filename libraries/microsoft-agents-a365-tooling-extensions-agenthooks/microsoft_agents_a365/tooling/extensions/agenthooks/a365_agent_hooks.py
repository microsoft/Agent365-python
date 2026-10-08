# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Agent 365 protection helpers for agent-hooks hosts."""

from __future__ import annotations

from typing import Final

from agent_hooks import CompositionConfig, EnforcementMode, InterceptionEmitter, SynthesisPolicy
from microsoft_agents_a365.tooling.protection.defender import DefenderRtpOptions

from .a365_defender_interceptor import A365DefenderInterceptor

_INTERCEPTOR_TIMEOUT_MARGIN_SECONDS: Final[float] = 2.0


def create_protection_emitter(
    *,
    interceptor_timeout_seconds: float | None = None,
    defender: DefenderRtpOptions | None = None,
) -> InterceptionEmitter:
    """Create an emitter for Agent 365 protection.

    The emitter uses enforce mode and the ``parallel/strictest`` profile: an action proceeds
    only when every interceptor allows it.

    Args:
        interceptor_timeout_seconds: Per-interceptor timeout, in seconds. Defaults to the
            Defender timeout plus two seconds, so the client's own timeout and fail mode apply
            first.
        defender: The Defender options whose timeout sets the default.

    Returns:
        The configured emitter.
    """
    if interceptor_timeout_seconds is None:
        defender_timeout = (defender or DefenderRtpOptions()).timeout_seconds
        interceptor_timeout_seconds = defender_timeout + _INTERCEPTOR_TIMEOUT_MARGIN_SECONDS

    return InterceptionEmitter(
        mode=EnforcementMode.ENFORCE,
        timeout=interceptor_timeout_seconds,
        composition=CompositionConfig.strictest(SynthesisPolicy.DENY),
    )


def add_a365_defender(
    emitter: InterceptionEmitter, interceptor: A365DefenderInterceptor
) -> InterceptionEmitter:
    """Register the Defender interceptor under the name ``defender``.

    Args:
        emitter: The emitter.
        interceptor: The Defender interceptor.

    Returns:
        The emitter.
    """
    if emitter is None:
        raise TypeError("emitter is required.")

    if interceptor is None:
        raise TypeError("interceptor is required.")

    return emitter.register(interceptor, A365DefenderInterceptor.NAME)

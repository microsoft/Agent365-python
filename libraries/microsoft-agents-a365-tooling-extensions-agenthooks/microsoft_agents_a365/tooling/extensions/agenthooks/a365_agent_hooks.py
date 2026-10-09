# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Agent 365 protection helpers for agent-hooks hosts."""

from __future__ import annotations

import math
from typing import Final

from agent_hooks import CompositionConfig, EnforcementMode, InterceptionEmitter, SynthesisPolicy
from microsoft_agents_a365.tooling.protection.defender import DefenderRtpOptions
from microsoft_agents_a365.tooling.protection.purview import PurviewDlpOptions

from .a365_defender_interceptor import A365DefenderInterceptor
from .a365_purview_interceptor import A365PurviewInterceptor

_INTERCEPTOR_TIMEOUT_MARGIN_SECONDS: Final[float] = 2.0


def create_protection_emitter(
    *,
    interceptor_timeout_seconds: float | None = None,
    defender: DefenderRtpOptions | None = None,
    purview: PurviewDlpOptions | None = None,
) -> InterceptionEmitter:
    """Create an emitter for Agent 365 protection.

    The emitter uses enforce mode and the ``parallel/strictest`` profile: an action proceeds
    only when every interceptor allows it, so Defender and Purview registered on one emitter
    compose with deny winning.

    Args:
        interceptor_timeout_seconds: Per-interceptor timeout, in seconds. Defaults to the
            Defender timeout (the Defender default when no Defender options are given) plus two
            seconds; when the given Purview options are enabled, to the slower of the Defender
            and Purview timeouts plus two seconds. Each client's own timeout and fail mode so
            apply first.
        defender: The Defender options whose timeout sets the default.
        purview: The Purview options whose timeout, when Purview DLP is enabled, also sets the
            default; a disabled Purview client makes no calls.

    Returns:
        The configured emitter.

    Raises:
        ValueError: If the interceptor timeout is not a positive, finite number of seconds.
    """
    if interceptor_timeout_seconds is None:
        slowest = (defender or DefenderRtpOptions()).timeout_seconds
        if purview is not None and purview.enabled:
            # max() would drop a NaN; keep it, so an invalid timeout is rejected below.
            purview_timeout = purview.timeout_seconds
            slowest = (
                math.nan
                if math.isnan(slowest) or math.isnan(purview_timeout)
                else max(slowest, purview_timeout)
            )

        interceptor_timeout_seconds = slowest + _INTERCEPTOR_TIMEOUT_MARGIN_SECONDS

    # agent-hooks accepts any float; NaN or infinity would leave a host without a timeout.
    if (
        isinstance(interceptor_timeout_seconds, bool)
        or not isinstance(interceptor_timeout_seconds, int | float)
        or not 0 < interceptor_timeout_seconds < math.inf
    ):
        raise ValueError("interceptor_timeout_seconds must be a positive, finite number.")

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


def add_a365_purview(
    emitter: InterceptionEmitter, interceptor: A365PurviewInterceptor
) -> InterceptionEmitter:
    """Register the Purview interceptor under the name ``purview``.

    Args:
        emitter: The emitter.
        interceptor: The Purview interceptor.

    Returns:
        The emitter.
    """
    if emitter is None:
        raise TypeError("emitter is required.")

    if interceptor is None:
        raise TypeError("interceptor is required.")

    return emitter.register(interceptor, A365PurviewInterceptor.NAME)

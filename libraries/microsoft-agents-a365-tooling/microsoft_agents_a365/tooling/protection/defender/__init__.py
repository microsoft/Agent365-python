# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Defender for AI real-time protection (Defender RTP).

The prevention endpoint (``POST .../v1/protection/evaluate``) takes an agent-hooks/0.1 context
and returns a verdict. :class:`DefenderRtpClient` forwards contexts emitted by an agent-hooks host
as the agent identity, at the four points Defender evaluates: ``input``, ``pre_tool_call``,
``post_tool_call`` and ``output``.

This module does not depend on agent-hooks; the interceptor that plugs the client into an
agent-hooks emitter is in ``microsoft-agents-a365-tooling-extensions-agenthooks``.
"""

from .defender_rtp_agent_context import DefenderRtpAgentContext, DefenderRtpTokenResolver
from .defender_rtp_client import DefenderRtpClient
from .defender_rtp_evaluation_result import (
    DefenderRtpEvaluationResult,
    DefenderRtpVerdict,
    DefenderRtpWarning,
)
from .defender_rtp_options import (
    DEFAULT_AUTHENTICATION_SCOPE,
    DEFENDER_API_APP_ID,
    DefenderRtpOptions,
)
from .defender_rtp_token_resolvers import DefenderRtpTokenResolvers

__all__ = [
    "DEFAULT_AUTHENTICATION_SCOPE",
    "DEFENDER_API_APP_ID",
    "DefenderRtpAgentContext",
    "DefenderRtpClient",
    "DefenderRtpEvaluationResult",
    "DefenderRtpOptions",
    "DefenderRtpTokenResolver",
    "DefenderRtpTokenResolvers",
    "DefenderRtpVerdict",
    "DefenderRtpWarning",
]

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Purview data loss prevention (DLP) of agent content.

:class:`PurviewDlpClient` sends agent content to the Microsoft Graph ``processContent`` API
(``POST .../dataSecurityAndGovernance/processContent``): the user's message as ``uploadText`` and
the agent's reply as ``downloadText``. Purview applies the tenant's DLP policies for the agent's
application, records the Purview audit event, and returns the policy actions; a ``block``
restriction blocks the content.

This module does not depend on agent-hooks; the interceptor that plugs the client into an
agent-hooks emitter is in ``microsoft-agents-a365-tooling-extensions-agenthooks``.
"""

from .purview_dlp_agent_context import (
    PurviewDlpAgentContext,
    PurviewDlpToken,
    PurviewDlpTokenResolver,
)
from .purview_dlp_client import PurviewDlpClient
from .purview_dlp_evaluation_result import (
    PurviewDlpActivity,
    PurviewDlpDecision,
    PurviewDlpEvaluationResult,
)
from .purview_dlp_options import (
    DEFAULT_AUTHENTICATION_SCOPE,
    DEFAULT_GRAPH_BASE_URL,
    PurviewDlpOptions,
    PurviewDlpResponseMode,
)
from .purview_dlp_token_resolvers import PurviewDlpAccessTokenProvider, PurviewDlpTokenResolvers

__all__ = [
    "DEFAULT_AUTHENTICATION_SCOPE",
    "DEFAULT_GRAPH_BASE_URL",
    "PurviewDlpAccessTokenProvider",
    "PurviewDlpActivity",
    "PurviewDlpAgentContext",
    "PurviewDlpClient",
    "PurviewDlpDecision",
    "PurviewDlpEvaluationResult",
    "PurviewDlpOptions",
    "PurviewDlpResponseMode",
    "PurviewDlpToken",
    "PurviewDlpTokenResolver",
    "PurviewDlpTokenResolvers",
]

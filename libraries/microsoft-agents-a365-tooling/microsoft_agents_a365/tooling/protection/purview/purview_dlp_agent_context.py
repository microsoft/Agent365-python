# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""The agent a Purview evaluation is made for, the Graph token it is made with, and the token
resolver type."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PurviewDlpAgentContext:
    """Identity of the agent an evaluation is made for.

    Attributes:
        agent_id: The agent identity (application) id, for example
            ``activity.get_agentic_instance_id()``. Sent as the agent's ``identifier``, and the
            identity the agentic user's token is requested through.
        tenant_id: The agent's tenant id.
        agentic_user_id: The agent's agentic user (its Entra user object id), for example
            ``activity.get_agentic_user()``. Required by
            :meth:`PurviewDlpTokenResolvers.from_agentic_user`, which evaluates as this user.
        blueprint_id: The agent blueprint (application) id, sent as the agent's ``blueprintId``;
            left out when unknown.
        application_id: The Entra application id the Purview DLP policies are scoped to (the
            request's ``applicationLocation``). Defaults to ``blueprint_id``, then ``agent_id``.
        agent_name: The agent's display name; names the agent, the app and the content entry in
            Purview, which requires a name. When it is not set, the agent-hooks interceptor uses
            the context's ``agent.name``, and the client ``agent_id``.
        agent_version: The agent's version, sent with its name; defaults to ``1.0``.
    """

    agent_id: str
    tenant_id: str
    agentic_user_id: str | None = None
    blueprint_id: str | None = None
    application_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None


@dataclass(frozen=True)
class PurviewDlpToken:
    """A Microsoft Graph access token, and the user ``processContent`` is called for.

    Attributes:
        access_token: The Graph access token: delegated with ``Content.Process.User``, or an
            application token for ``/users/{user_id}``. Never shown in ``repr``.
        user_id: The user to evaluate as (``/users/{user_id}``). ``None`` evaluates as the
            token's own user (``/me``), which needs a delegated token.
    """

    access_token: str = field(repr=False)
    user_id: str | None = None


PurviewDlpTokenResolver = Callable[
    [PurviewDlpAgentContext, list[str]],
    Awaitable[PurviewDlpToken | None] | PurviewDlpToken | None,
]
"""Resolves the Microsoft Graph token for a Purview evaluation.

Called with ``(agent, scopes)``: the agent the evaluation is for and the scopes to request
(:attr:`PurviewDlpOptions.authentication_scope`). Returns the token and the user to evaluate as,
or ``None`` when none is available. May be sync or async; a synchronous resolver runs on a worker
thread, so the evaluation deadline applies while it blocks.

See :class:`PurviewDlpTokenResolvers`: ``from_agentic_user`` evaluates as the agent's agentic user
(``/me``) with its delegated token, and ``from_access_token_provider`` uses a token the host
supplies.
"""

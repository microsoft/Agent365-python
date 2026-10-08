# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""The agent identity a Defender evaluation is made for, and its token resolver type."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

DefenderRtpTokenResolver = Callable[[str, str, list[str]], Awaitable[str | None] | str | None]
"""Resolves the access token for a Defender evaluation.

Called with ``(agent_id, tenant_id, scopes)``: the agent identity (application) id, which is the
token's ``appid``; the agent's tenant, which must equal the context's ``tenant.id``; and the scopes
to request. Returns the agent identity's own app-only token for the Defender API, carrying the
``RealtimeProtection.Evaluate.All`` role, or ``None`` when none is available. May be sync or async;
a synchronous resolver runs on a worker thread, so the evaluation deadline applies while it blocks.

Use the same authority as Observability S2S export: the blueprint credential obtains the agent
identity's assertion (FMI), and the agent identity exchanges it for the requested scope (see
:meth:`DefenderRtpTokenResolvers.from_agentic_connection`). The client caches the returned token
per agent, tenant and scope until shortly before it expires.
"""


@dataclass(frozen=True)
class DefenderRtpAgentContext:
    """Identity of the agent and turn an evaluation is for.

    Fills context fields a host did not set.

    Attributes:
        agent_id: The agent identity (application) id the token is requested for.
        tenant_id: The agent's tenant id; sent as ``tenant.id`` and used to acquire the token.
        agent_object_id: The agent's Entra object id, sent as ``agent.id``. Defaults to the
            context's ``agent.id``, then ``agent_id`` (equal for Agent ID agent identities).
        agent_name: The agent's display name (``agent.name``) when the context has none.
        framework: The agent framework (``agent.framework``, lowercase ``[a-z0-9_-]``) when the
            context has none.
        request_id: The turn's request id (``request_id``), for example the activity id.
        user_id: Who triggered the run (``actor.id``), for example the user's Entra object id.
        actor_kind: The kind of actor (``actor.kind``): ``human`` (default), ``service`` for
            autonomous runs, or ``agent`` for agent-to-agent calls.
        model_name: The model the agent uses (``model.id``) when the context has none.
    """

    agent_id: str
    tenant_id: str
    agent_object_id: str | None = None
    agent_name: str | None = None
    framework: str | None = None
    request_id: str | None = None
    user_id: str | None = None
    actor_kind: str | None = None
    model_name: str | None = None

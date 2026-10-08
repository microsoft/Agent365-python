# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Token resolvers for :class:`DefenderRtpClient`."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Final
from urllib.parse import quote

import aiohttp
from microsoft_agents.hosting.core import AccessTokenProviderBase

from ._http import http_session
from .defender_rtp_agent_context import DefenderRtpTokenResolver
from .defender_rtp_options import is_https_url

_CLIENT_ASSERTION_TYPE: Final[str] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
_DEFAULT_AUTHORITY: Final[str] = "https://login.microsoftonline.com"


class DefenderRtpTokenResolvers:
    """Token resolvers for :class:`DefenderRtpClient`."""

    @staticmethod
    def from_agentic_connection(
        connection: AccessTokenProviderBase,
        session: aiohttp.ClientSession | None = None,
        authority: str = _DEFAULT_AUTHORITY,
    ) -> DefenderRtpTokenResolver:
        """The agent identity's own app-only token, in the agent's tenant.

        The token is issued through the agent's Agents SDK connection: the connection's
        blueprint credential (secret, certificate, federated or managed identity) issues the
        agent identity's assertion (``get_agentic_application_token``), which is exchanged for
        the Defender API token. This is the same authority Observability S2S export uses.

        ``microsoft-agents-hosting-core`` 0.8 and later pass the agent's tenant to
        ``get_agentic_application_token(tenant_id, agent_app_instance_id)``; 0.7 takes only the
        agent identity and issues the assertion in the connection's configured tenant.

        Args:
            connection: The agent's connection, for example
                ``connection_manager.get_default_connection()`` (``MsalAuth`` implements
                ``get_agentic_application_token``).
            session: The HTTP session for the token endpoint; a pooled session owned by the
                caller is recommended. When omitted, each request opens its own session.
            authority: The Entra authority; defaults to ``https://login.microsoftonline.com``.

        Returns:
            A resolver for :meth:`DefenderRtpClient.evaluate_hook_context`.

        Raises:
            ValueError: If ``authority`` is not an absolute HTTPS URL.
        """
        if connection is None:
            raise TypeError("connection is required.")

        if not is_https_url(authority):
            raise ValueError("authority must be an absolute HTTPS URL.")

        get_assertion: Callable[..., Awaitable[str | None]] = (
            connection.get_agentic_application_token
        )
        takes_tenant = _accepts_tenant(get_assertion)
        base_authority = authority.rstrip("/")

        async def resolve(agent_id: str, tenant_id: str, scopes: list[str]) -> str | None:
            assertion = await (
                get_assertion(tenant_id, agent_id) if takes_tenant else get_assertion(agent_id)
            )
            if not isinstance(assertion, str) or not assertion:
                raise RuntimeError("The agent connection returned no agent identity assertion.")

            form = {
                "grant_type": "client_credentials",
                "client_id": agent_id,
                "client_assertion_type": _CLIENT_ASSERTION_TYPE,
                "client_assertion": assertion,
                "scope": " ".join(scopes),
            }
            url = f"{base_authority}/{quote(tenant_id, safe='')}/oauth2/v2.0/token"
            async with http_session(session) as http:
                # No redirects: a 307/308 would resend the assertion to a target that never
                # passed the HTTPS check; a 3xx is a token failure.
                async with http.post(url, data=form, allow_redirects=False) as response:
                    status = response.status
                    body = await response.read()

            # Never surface the response body: it can echo the assertion.
            if not 200 <= status < 300:
                raise RuntimeError(f"The Defender token request failed with HTTP {status}.")

            try:
                payload: object = json.loads(body)
            except (ValueError, RecursionError):
                payload = None

            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(token, str) or not token:
                raise RuntimeError("The Defender token response had no access_token.")

            return token

        return resolve


def _accepts_tenant(get_assertion: Callable[..., object]) -> bool:
    """Whether ``get_agentic_application_token`` takes the tenant (hosting-core 0.8+)."""
    try:
        parameters = list(inspect.signature(get_assertion).parameters.values())
    except (TypeError, ValueError):
        return True

    if any(parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return True

    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2

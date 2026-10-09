# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Token resolvers for :class:`PurviewDlpClient`."""

from __future__ import annotations

import asyncio
import base64
import functools
import inspect
import json
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

from microsoft_agents.hosting.core import AccessTokenProviderBase

from .purview_dlp_agent_context import (
    PurviewDlpAgentContext,
    PurviewDlpToken,
    PurviewDlpTokenResolver,
)
from .purview_dlp_options import DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

PurviewDlpAccessTokenProvider = Callable[[list[str]], Awaitable[str | None] | str | None]
"""Returns a Microsoft Graph access token for the given scopes; may be sync or async."""

_CacheKey = tuple[str, str, str, str]

_MAX_CACHED_TOKENS: Final[int] = 100
_TOKEN_REFRESH_SKEW_SECONDS: Final[float] = 300.0


class PurviewDlpTokenResolvers:
    """Token resolvers for :class:`PurviewDlpClient`."""

    @staticmethod
    def from_agentic_user(
        connection: AccessTokenProviderBase,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> PurviewDlpTokenResolver:
        """The agent's agentic user's delegated Microsoft Graph token; evaluates as ``/me``.

        The token is issued through the agent's Agents SDK connection
        (``get_agentic_user_token``): the connection's blueprint credential (secret,
        certificate, federated or managed identity) issues the agent identity's assertion, which
        is exchanged for the agentic user's token (``user_fic``). The agentic user needs the
        delegated ``Content.Process.User`` permission, which it inherits from the agent
        blueprint's Microsoft Graph grant.

        ``microsoft-agents-hosting-core`` 0.8 and later pass the agent's tenant to
        ``get_agentic_user_token(tenant_id, agent_app_instance_id, agentic_user_id, scopes)``;
        earlier releases take ``(agent_app_instance_id, agentic_user_id, scopes)`` and issue the
        token in the connection's configured tenant.

        Tokens are cached per tenant, agent, agentic user and scopes until shortly before they
        expire, so create the resolver once and reuse it. One acquisition per key runs at a time
        and is shared by concurrent evaluations; a failed one is never cached. Within five minutes
        of expiry, an evaluation refreshes the token in the background and keeps using the cached
        one, also when the refresh fails.

        Args:
            connection: The agent's connection, for example
                ``connection_manager.get_default_connection()`` (``MsalAuth`` implements
                ``get_agentic_user_token``).
            timeout_seconds: Bounds each token acquisition, which continues in the background
                when an evaluation's deadline passes first.
            clock: Returns the current time in seconds since the epoch (tests).

        Returns:
            A resolver for :meth:`PurviewDlpClient.evaluate`. It requires
            :attr:`PurviewDlpAgentContext.agentic_user_id`.

        Raises:
            ValueError: If ``timeout_seconds`` is not a positive, finite number.
        """
        if connection is None:
            raise TypeError("connection is required.")

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or not 0 < timeout_seconds < math.inf
        ):
            raise ValueError("timeout_seconds must be a positive, finite number.")

        get_user_token: Callable[..., Awaitable[str | None] | str | None] = (
            connection.get_agentic_user_token
        )
        takes_tenant = _accepts_tenant(get_user_token)
        cache = _TokenCache(timeout_seconds, clock or time.time)

        async def resolve(agent: PurviewDlpAgentContext, scopes: list[str]) -> PurviewDlpToken:
            tenant_id = _require_text(agent.tenant_id, "tenant_id")
            agent_id = _require_text(agent.agent_id, "agent_id")
            agentic_user_id = _require_text(agent.agentic_user_id, "agentic_user_id")
            requested = list(scopes)

            async def acquire() -> str:
                issued = (
                    get_user_token(tenant_id, agent_id, agentic_user_id, requested)
                    if takes_tenant
                    else get_user_token(agent_id, agentic_user_id, requested)
                )
                token = await issued if inspect.isawaitable(issued) else issued
                if not isinstance(token, str) or not token.strip():
                    raise RuntimeError("The agent connection returned no agentic user token.")

                return token

            # The token is the agentic user's, fully determined by these ids and the scopes.
            key: _CacheKey = (
                tenant_id.lower(),
                agent_id.lower(),
                agentic_user_id.lower(),
                " ".join(requested),
            )
            return PurviewDlpToken(await cache.get(key, acquire))

        return resolve

    @staticmethod
    def from_access_token_provider(
        get_token: PurviewDlpAccessTokenProvider,
        user_id: str | None = None,
    ) -> PurviewDlpTokenResolver:
        """A Microsoft Graph token the host supplies.

        For example an on-behalf-of token for the signed-in user (evaluates as ``/me``), or an
        application token (application permission ``Content.Process.User`` or
        ``Content.Process.All``) with the user to evaluate as (``/users/{user_id}``; this
        application path has not been validated end to end yet).
        The provider is called for every evaluation and should cache its tokens (MSAL does); a
        synchronous provider runs on a worker thread and should bound its own blocking.

        Args:
            get_token: Returns a Graph token for the given scopes; may be sync or async.
            user_id: The user to evaluate as, for an application token; ``None`` evaluates as
                the token's own user (``/me``).

        Returns:
            A resolver for :meth:`PurviewDlpClient.evaluate`.

        Raises:
            ValueError: If ``user_id`` is empty.
        """
        if not callable(get_token):
            raise TypeError("get_token must be callable.")

        if user_id is not None and _text(user_id) is None:
            raise ValueError("user_id must not be empty.")

        async def resolve(_agent: PurviewDlpAgentContext, scopes: list[str]) -> PurviewDlpToken:
            requested = list(scopes)
            issued: object
            if inspect.iscoroutinefunction(get_token):
                issued = get_token(requested)
            else:
                # A synchronous provider would block the event loop, where the deadline cannot
                # interrupt it.
                issued = await asyncio.to_thread(get_token, requested)

            token = await issued if inspect.isawaitable(issued) else issued
            if not isinstance(token, str) or not token.strip():
                raise RuntimeError("The access token provider returned no token.")

            return PurviewDlpToken(token, user_id)

        return resolve


@dataclass(frozen=True)
class _CachedToken:
    token: str = field(repr=False)
    expires_at: float


class _TokenCache:
    """Tokens per key until shortly before they expire, with one acquisition per key at a time.

    An acquisition is bounded by its own timeout and not tied to any single caller's
    cancellation, so it can finish (and be cached) after a caller's deadline passed; it is
    dropped when it completes, and a failed one is never cached.
    """

    def __init__(self, timeout_seconds: float, clock: Callable[[], float]) -> None:
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._tokens: dict[_CacheKey, _CachedToken] = {}
        self._in_flight: dict[_CacheKey, asyncio.Future[str]] = {}

    async def get(self, key: _CacheKey, acquire: Callable[[], Awaitable[str]]) -> str:
        cached = self._tokens.get(key)
        now = self._clock()
        if cached is not None and now < cached.expires_at:
            if now >= cached.expires_at - _TOKEN_REFRESH_SKEW_SECONDS:
                # Refresh ahead without waiting: the cached token stays in use until it expires,
                # including when the refresh fails.
                refresh, started = self._acquisition(key, acquire)
                if started:
                    refresh.add_done_callback(_log_failed_refresh)

            return cached.token

        acquisition, _ = self._acquisition(key, acquire)
        return await asyncio.shield(acquisition)

    def _acquisition(
        self, key: _CacheKey, acquire: Callable[[], Awaitable[str]]
    ) -> tuple[asyncio.Future[str], bool]:
        """The in-flight acquisition for ``key``, and whether this call started it."""
        acquisition = self._in_flight.get(key)
        if acquisition is not None:
            return acquisition, False

        acquisition = asyncio.ensure_future(self._acquire(key, acquire))
        self._in_flight[key] = acquisition
        acquisition.add_done_callback(functools.partial(self._acquisition_done, key))
        return acquisition, True

    def _acquisition_done(self, key: _CacheKey, acquisition: asyncio.Future[str]) -> None:
        if self._in_flight.get(key) is acquisition:
            del self._in_flight[key]

        # Every caller may have been cancelled; retrieve the failure so it is not reported as
        # never retrieved.
        if not acquisition.cancelled():
            acquisition.exception()

    async def _acquire(self, key: _CacheKey, acquire: Callable[[], Awaitable[str]]) -> str:
        async with asyncio.timeout(self._timeout_seconds):
            token = await acquire()

        expires_at = _read_expiry(token)
        if expires_at is not None:
            now = self._clock()
            if expires_at <= now:
                raise RuntimeError("The agent connection returned an expired token.")

            if len(self._tokens) >= _MAX_CACHED_TOKENS:
                for stale in [k for k, v in self._tokens.items() if v.expires_at <= now]:
                    del self._tokens[stale]

                if len(self._tokens) >= _MAX_CACHED_TOKENS:
                    del self._tokens[min(self._tokens, key=lambda k: self._tokens[k].expires_at)]

            self._tokens[key] = _CachedToken(token, expires_at)

        return token


def _log_failed_refresh(refresh: asyncio.Future[str]) -> None:
    if not refresh.cancelled() and refresh.exception() is not None:
        logger.warning(
            "Purview DLP token refresh failed (%s); the cached token is used until it expires.",
            type(refresh.exception()).__name__,
        )


def _accepts_tenant(get_user_token: Callable[..., object]) -> bool:
    """Whether ``get_agentic_user_token`` takes the tenant (hosting-core 0.8+)."""
    try:
        parameters = list(inspect.signature(get_user_token).parameters.values())
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
    return len(positional) >= 4


def _read_expiry(token: str) -> float | None:
    """The ``exp`` claim of a JWT, in seconds since the epoch; ``None`` when unreadable."""
    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims: object = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, RecursionError):
        return None

    expiry = claims.get("exp") if isinstance(claims, dict) else None
    if isinstance(expiry, bool) or not isinstance(expiry, int | float):
        return None

    try:
        seconds = float(expiry)
    except OverflowError:
        return None

    return seconds if math.isfinite(seconds) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _require_text(value: object, name: str) -> str:
    text = _text(value)
    if text is None:
        raise ValueError(f"{name} is required.")

    return text

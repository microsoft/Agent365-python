# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""App-only token cache for Agent 365 observability export."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from inspect import isawaitable
from threading import Lock

from microsoft_agents.hosting.core.app.oauth.authorization import Authorization
from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.runtime.environment_utils import get_observability_authentication_scope

logger = logging.getLogger(__name__)

ObservabilityTokenResolver = Callable[[str, str, Sequence[str]], str | Awaitable[str | None] | None]


@dataclass
class AgenticTokenStruct:
    """Deprecated delegated OBS token generator shape.

    OBS export is S2S-only. Instances of this type are accepted only for source
    compatibility; the cache never calls ``authorization.exchange_token``.
    """

    authorization: Authorization
    """The user authorization object from the removed delegated OBS flow."""

    turn_context: TurnContext
    """The turn context from the removed delegated OBS flow."""

    auth_handler_name: str | None = "AGENTIC"
    """The name of the removed delegated authentication handler."""


class AgenticTokenCache:
    """Caches app-only OBS tokens per ``(agent_id, tenant_id)``.

    Call :meth:`refresh_observability_token` from the exporter's token resolver
    to acquire or refresh an app-only token. The resolver receives the exporting
    agent ID, tenant ID, and OBS ``/.default`` scopes. Delegated TurnContext /
    Authorization shapes are logged once and ignored.
    """

    @dataclass
    class _Entry:
        """Internal entry structure for cache storage."""

        scopes: tuple[str, ...]
        token: str | None = None
        expires_on_ms: float | None = None
        acquired_on_ms: float | None = None
        lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    _default_refresh_skew_ms = 60_000
    _default_max_token_age_ms = 3_600_000
    _max_exp_seconds = 86_400
    _max_cache_size = 10_000

    def __init__(self, observability_scopes: Sequence[str] | None = None) -> None:
        """Initialize the token cache."""
        self._map: dict[tuple[str, str], AgenticTokenCache._Entry] = {}
        self._lock = Lock()
        self._observability_scopes = (
            None if observability_scopes is None else tuple(observability_scopes)
        )
        self._removed_registration_logged = False

    @staticmethod
    def _make_key(agent_id: str, tenant_id: str) -> tuple[str, str]:
        # A tuple key keeps identities apart even when an ID contains a separator character.
        return (agent_id, tenant_id)

    def register_observability(
        self,
        agent_id: str,
        tenant_id: str,
        token_generator: AgenticTokenStruct,
        observability_scopes: list[str],
    ) -> None:
        """Deprecated no-op for the removed delegated OBS registration flow."""
        self._log_removed_registration_once()

    async def refresh_observability_token(
        self,
        agent_id: str,
        tenant_id: str,
        token_resolver: ObservabilityTokenResolver,
    ) -> str:
        """Refresh an app-only OBS token for the exporting agent identity.

        Args:
            agent_id: The exporting agent instance identifier.
            tenant_id: The exporting tenant identifier.
            token_resolver: App-only token resolver receiving ``(agent_id,
                tenant_id, scopes)``.

        Returns:
            The cached app-only OBS token.

        Raises:
            TypeError: If ``token_resolver`` is not callable.
            ValueError: If agent or tenant IDs are empty, or no scopes are configured.
            Exception: Propagates resolver failures after retry handling.
        """
        if not callable(token_resolver):
            raise TypeError("token_resolver must be callable")

        if not agent_id or not agent_id.strip() or not tenant_id or not tenant_id.strip():
            raise ValueError("[AgenticTokenCache] Agent and tenant IDs are required")

        key = self._make_key(agent_id, tenant_id)
        entry = self._get_or_create_entry(key)
        async with entry.lock:
            if entry.token is not None and not self._is_expired(entry):
                return entry.token

            return await self._acquire_token(agent_id, tenant_id, entry, token_resolver)

    async def get_observability_token(self, agent_id: str, tenant_id: str) -> str | None:
        """Return a non-expired cached app-only OBS token, or ``None``.

        This method is a pure cache read. It never acquires a token and never
        calls delegated token exchange.
        """
        key = self._make_key(agent_id, tenant_id)
        with self._lock:
            entry = self._map.get(key)

        if entry is None or entry.token is None:
            logger.debug("[AgenticTokenCache] No token cached for %s", key)
            return None
        if self._is_expired(entry):
            logger.debug("[AgenticTokenCache] Token expired for %s", key)
            return None
        return entry.token

    def invalidate_token(self, agent_id: str, tenant_id: str) -> None:
        """Invalidate one cached token."""
        key = self._make_key(agent_id, tenant_id)
        with self._lock:
            entry = self._map.get(key)
            if entry is not None:
                self._clear_token(entry)

    def invalidate_all(self) -> None:
        """Invalidate all cached tokens."""
        with self._lock:
            self._map.clear()

    def _get_or_create_entry(self, key: tuple[str, str]) -> _Entry:
        with self._lock:
            entry = self._map.get(key)
            if entry is not None:
                if not entry.scopes:
                    raise ValueError("[AgenticTokenCache] Entry has invalid scopes")
                return entry

            scopes = self._get_effective_scopes()
            if not scopes:
                raise ValueError("[AgenticTokenCache] No valid scopes")

            if len(self._map) >= self._max_cache_size:
                # Evict the oldest idle entry; an entry with a refresh in flight keeps its lock.
                idle_key = next(
                    (
                        existing_key
                        for existing_key, existing in self._map.items()
                        if not existing.lock.locked()
                    ),
                    None,
                )
                if idle_key is not None:
                    del self._map[idle_key]

            entry = AgenticTokenCache._Entry(scopes=scopes)
            self._map[key] = entry
            return entry

    def _get_effective_scopes(self) -> tuple[str, ...]:
        scopes = self._observability_scopes
        if scopes is None:
            scopes = tuple(get_observability_authentication_scope())
        return tuple(scope for scope in scopes if scope and scope.strip())

    async def _acquire_token(
        self,
        agent_id: str,
        tenant_id: str,
        entry: _Entry,
        resolver: ObservabilityTokenResolver,
    ) -> str:
        max_retries = 2
        last_error: BaseException | None = None
        for attempt in range(max_retries + 1):
            logger.info(
                "[AgenticTokenCache] Acquiring app-only token attempt %s/%s",
                attempt + 1,
                max_retries + 1,
            )
            try:
                result = resolver(agent_id, tenant_id, list(entry.scopes))
                token = await result if isawaitable(result) else result
                if token is None or not token.strip():
                    raise RuntimeError(
                        "[AgenticTokenCache] App-only token resolver returned no token"
                    )
                entry.token = token
                entry.acquired_on_ms = time.time() * 1000
                exp = self._decode_exp(token)
                if exp is not None:
                    entry.expires_on_ms = exp * 1000
                else:
                    entry.expires_on_ms = None
                    logger.warning("[AgenticTokenCache] No exp claim, fallback TTL")
                logger.info("[AgenticTokenCache] Token cached")
                return token
            except Exception as error:
                last_error = error
                if self._is_retriable_error(error) and attempt < max_retries:
                    logger.warning(
                        "[AgenticTokenCache] Retriable token acquisition failure attempt %s: %s",
                        attempt + 1,
                        error,
                    )
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                logger.error("[AgenticTokenCache] Token acquisition failed: %s", error)
                self._clear_token(entry)
                raise

        self._clear_token(entry)
        raise RuntimeError("[AgenticTokenCache] Token acquisition failed") from last_error

    def _decode_exp(self, jwt: str) -> int | None:
        try:
            parts = jwt.split(".")
            if len(parts) < 2:
                return None
            payload = parts[1]
            padded = payload + "=" * ((4 - (len(payload) % 4)) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
            claims = json.loads(decoded.decode("utf-8"))
            if not isinstance(claims, dict):
                return None
            exp = claims.get("exp")
            if not isinstance(exp, int | float):
                return None
            max_exp = int(time.time()) + self._max_exp_seconds
            return min(int(exp), max_exp)
        except Exception:
            return None

    def _is_expired(self, entry: _Entry) -> bool:
        now = time.time() * 1000
        if entry.expires_on_ms is not None:
            return now >= entry.expires_on_ms - self._default_refresh_skew_ms
        if entry.acquired_on_ms is not None:
            return now >= entry.acquired_on_ms + self._default_max_token_age_ms
        return True

    def _is_retriable_error(self, error: Exception) -> bool:
        message = str(error).lower()
        if "timeout" in message or "econnreset" in message or "network" in message:
            return True

        status = self._get_status(error)
        return status in (408, 429) or (status is not None and 500 <= status < 600)

    def _get_status(self, error: Exception) -> int | None:
        for name in ("status", "status_code"):
            value = getattr(error, name, None)
            if isinstance(value, int):
                return value
        return None

    def _clear_token(self, entry: _Entry) -> None:
        entry.token = None
        entry.expires_on_ms = None
        entry.acquired_on_ms = None

    def _log_removed_registration_once(self) -> None:
        if self._removed_registration_logged:
            return
        self._removed_registration_logged = True
        logger.error(
            "[AgenticTokenCache] Delegated OBS token registration was removed and does "
            "nothing; S2S OBS needs an app-only token. Call "
            "refresh_observability_token(agent_id, tenant_id, token_resolver) instead."
        )

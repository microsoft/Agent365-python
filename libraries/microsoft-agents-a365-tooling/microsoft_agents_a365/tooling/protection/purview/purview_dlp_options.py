# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Configuration for Microsoft Purview data loss prevention (DLP) of agent content."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final, Literal
from urllib.parse import urlparse

from ..defender.defender_rtp_options import is_https_url

PurviewDlpResponseMode = Literal["audit", "enforce"]
"""How the agent's reply is evaluated: ``audit`` sends it to Purview without waiting, and
``enforce`` waits for Purview's decision and blocks the reply when a policy blocks it."""

#: Default Microsoft Graph base URL that hosts ``processContent``.
DEFAULT_GRAPH_BASE_URL: Final[str] = "https://graph.microsoft.com/v1.0"

#: Default token scope: Microsoft Graph.
DEFAULT_AUTHENTICATION_SCOPE: Final[str] = "https://graph.microsoft.com/.default"

#: Default per-call timeout for token acquisition and evaluation, in seconds.
DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0

#: Default maximum characters of content sent to Purview per evaluation.
DEFAULT_MAX_CONTENT_CHARACTERS: Final[int] = 100000

ENABLE_VARIABLE: Final[str] = "ENABLE_A365_PURVIEW_DLP"
GRAPH_BASE_URL_VARIABLE: Final[str] = "A365_PURVIEW_DLP_GRAPH_BASE_URL"
AUTHENTICATION_SCOPE_VARIABLE: Final[str] = "A365_PURVIEW_DLP_AUTHENTICATION_SCOPE"
FAIL_MODE_VARIABLE: Final[str] = "A365_PURVIEW_DLP_FAIL_MODE"
TIMEOUT_VARIABLE: Final[str] = "A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS"
MAX_CONTENT_CHARACTERS_VARIABLE: Final[str] = "A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS"
RESPONSE_MODE_VARIABLE: Final[str] = "A365_PURVIEW_DLP_RESPONSE_MODE"

_INTEGER = re.compile(r"[+-]?\d+")
_ENABLED_VALUES: Final[frozenset[str]] = frozenset({"true", "1", "yes", "on"})
_DISABLED_VALUES: Final[frozenset[str]] = frozenset({"false", "0", "no", "off"})
_RESPONSE_MODES: Final[frozenset[str]] = frozenset({"audit", "enforce"})
# The largest timeout (in milliseconds) or content limit read, as in the other Agent 365 SDKs.
_MAX_INTEGER: Final[int] = 2**31 - 1
_MAX_TIMEOUT_SECONDS: Final[float] = _MAX_INTEGER / 1000


@dataclass
class PurviewDlpOptions:
    """Configuration for Microsoft Purview data loss prevention (DLP) of agent content.

    Each evaluation posts the content to the Microsoft Graph ``processContent`` API, which applies
    the tenant's Purview DLP policies for the agent and records the Purview audit event.

    Attributes:
        enabled: Whether Purview DLP is enabled (``ENABLE_A365_PURVIEW_DLP``).
        graph_base_url: The Microsoft Graph base URL (``A365_PURVIEW_DLP_GRAPH_BASE_URL``);
            defaults to ``https://graph.microsoft.com/v1.0``.
        authentication_scope: The token scope (``A365_PURVIEW_DLP_AUTHENTICATION_SCOPE``);
            defaults to Microsoft Graph.
        timeout_seconds: Per-call timeout for token acquisition and evaluation, in seconds
            (``A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS``, in milliseconds).
        fail_closed: When true, an evaluation that returns no decision blocks
            (``A365_PURVIEW_DLP_FAIL_MODE=closed``); otherwise it is allowed and reported as not
            evaluated.
        max_content_characters: Maximum characters of content sent per evaluation
            (``A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS``). Longer content is cut and sent
            flagged as truncated: Purview's block still blocks, but its allow follows the fail
            mode.
        response_mode: How the agent's reply is evaluated (``A365_PURVIEW_DLP_RESPONSE_MODE``):
            ``audit`` (default) sends it without waiting, since Purview DLP policies for AI apps
            restrict prompts, not replies; ``enforce`` waits and blocks a reply a policy blocks.
    """

    DEFAULT_GRAPH_BASE_URL: ClassVar[str] = DEFAULT_GRAPH_BASE_URL
    DEFAULT_AUTHENTICATION_SCOPE: ClassVar[str] = DEFAULT_AUTHENTICATION_SCOPE

    enabled: bool = False
    graph_base_url: str = DEFAULT_GRAPH_BASE_URL
    authentication_scope: str = DEFAULT_AUTHENTICATION_SCOPE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    fail_closed: bool = False
    max_content_characters: int = DEFAULT_MAX_CONTENT_CHARACTERS
    response_mode: PurviewDlpResponseMode = "audit"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> PurviewDlpOptions:
        """Read the options from environment variables.

        Args:
            environ: The variables to read; defaults to ``os.environ``.

        Returns:
            The configured options.

        Raises:
            ValueError: If the enable flag is not a recognized true or false (``true``/``false``,
                ``1``/``0``, ``yes``/``no``, ``on``/``off``), the Graph base URL is not an
                absolute HTTPS URL without a query or fragment, the fail mode is neither
                ``open`` nor ``closed``, the response mode is neither ``audit`` nor ``enforce``,
                or the timeout or the maximum content characters is not a positive integer of at
                most 2147483647.
        """
        variables = os.environ if environ is None else environ

        def read(name: str) -> str | None:
            value = variables.get(name)
            if value is None:
                return None
            value = value.strip()
            return value or None

        options = cls(
            enabled=_parse_enabled(read(ENABLE_VARIABLE)),
            fail_closed=_parse_fail_mode(read(FAIL_MODE_VARIABLE)),
            response_mode=_parse_response_mode(read(RESPONSE_MODE_VARIABLE)),
        )

        graph_base_url = read(GRAPH_BASE_URL_VARIABLE)
        if graph_base_url is not None:
            if not is_graph_base_url(graph_base_url):
                raise ValueError(
                    f"{GRAPH_BASE_URL_VARIABLE} must be an absolute HTTPS URL without a query or "
                    "fragment."
                )
            options.graph_base_url = graph_base_url.rstrip("/")

        scope = read(AUTHENTICATION_SCOPE_VARIABLE)
        if scope is not None:
            options.authentication_scope = scope

        timeout = read(TIMEOUT_VARIABLE)
        if timeout is not None:
            options.timeout_seconds = _parse_positive(timeout, TIMEOUT_VARIABLE) / 1000

        maximum = read(MAX_CONTENT_CHARACTERS_VARIABLE)
        if maximum is not None:
            options.max_content_characters = _parse_positive(
                maximum, MAX_CONTENT_CHARACTERS_VARIABLE
            )

        return options

    def validate(self) -> None:
        """Raise when the options cannot be used for a client.

        Raises:
            ValueError: If the Graph base URL is not an absolute HTTPS URL without a query or
                fragment, the timeout is not a positive, finite number of seconds (at most
                2147483.647), the maximum content characters is not a positive integer (at most
                2147483647), the authentication scope is missing, or the response mode is neither
                ``audit`` nor ``enforce``.
        """
        if not isinstance(self.graph_base_url, str) or not is_graph_base_url(self.graph_base_url):
            raise ValueError(
                "PurviewDlpOptions.graph_base_url must be an absolute HTTPS URL without a query "
                "or fragment."
            )

        timeout = self.timeout_seconds
        # NaN fails both comparisons, and infinity the upper bound: neither is a deadline.
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int | float)
            or not 0 < timeout <= _MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "PurviewDlpOptions.timeout_seconds must be a positive, finite number of at most "
                f"{_MAX_TIMEOUT_SECONDS} seconds."
            )

        maximum = self.max_content_characters
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or not 0 < maximum <= _MAX_INTEGER
        ):
            raise ValueError(
                "PurviewDlpOptions.max_content_characters must be a positive integer of at most "
                f"{_MAX_INTEGER}."
            )

        scope = self.authentication_scope
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("PurviewDlpOptions.authentication_scope is required.")

        if self.response_mode not in _RESPONSE_MODES:
            raise ValueError('PurviewDlpOptions.response_mode must be "audit" or "enforce".')


def is_graph_base_url(value: str) -> bool:
    """Whether ``value`` is an absolute HTTPS URL that a request path can be appended to, so
    tokens never travel in plaintext or to a path the URL did not name."""
    if not is_https_url(value):
        return False

    parsed = urlparse(value)
    return not parsed.query and not parsed.fragment and "?" not in value and "#" not in value


def _parse_enabled(value: str | None) -> bool:
    """Whether Purview DLP is enabled. Unset means disabled; a value that is not a recognized
    way of saying true or false is rejected, so a typo cannot quietly turn protection off."""
    if value is None or value.lower() in _DISABLED_VALUES:
        return False

    if value.lower() in _ENABLED_VALUES:
        return True

    raise ValueError(f"{ENABLE_VARIABLE} must be true or false.")


def _parse_fail_mode(value: str | None) -> bool:
    """Whether the fail mode is closed. Unset means open; any value but ``open`` or ``closed``
    is rejected, so a typo cannot silently turn blocking off."""
    if value is None or value.lower() == "open":
        return False

    if value.lower() == "closed":
        return True

    raise ValueError(f'{FAIL_MODE_VARIABLE} must be "open" or "closed".')


def _parse_response_mode(value: str | None) -> PurviewDlpResponseMode:
    """The response mode. Unset means ``audit``; any value but ``audit`` or ``enforce`` is
    rejected, so a typo cannot silently stop replies from being enforced."""
    if value is None or value.lower() == "audit":
        return "audit"

    if value.lower() == "enforce":
        return "enforce"

    raise ValueError(f'{RESPONSE_MODE_VARIABLE} must be "audit" or "enforce".')


def _parse_positive(value: str, name: str) -> int:
    if _INTEGER.fullmatch(value) is not None:
        parsed = int(value)
        if 0 < parsed <= _MAX_INTEGER:
            return parsed
    raise ValueError(f"{name} must be a positive integer of at most {_MAX_INTEGER}.")

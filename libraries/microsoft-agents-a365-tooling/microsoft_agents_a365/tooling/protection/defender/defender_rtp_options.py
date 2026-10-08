# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Configuration for Microsoft Defender for AI real-time protection (Defender RTP)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final
from urllib.parse import urlparse

#: Application id of the Defender API that grants ``RealtimeProtection.Evaluate.All``.
DEFENDER_API_APP_ID: Final[str] = "86a21212-634e-4553-b3d6-e477e4c9d9ec"

#: Default token scope: the Defender API.
DEFAULT_AUTHENTICATION_SCOPE: Final[str] = f"api://{DEFENDER_API_APP_ID}/.default"

#: Default per-call timeout for token acquisition and evaluation, in seconds.
DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0

#: Default maximum characters per string value sent to Defender.
DEFAULT_MAX_CONTENT_CHARACTERS: Final[int] = 20000

ENABLE_VARIABLE: Final[str] = "ENABLE_A365_DEFENDER_RTP"
ENDPOINT_VARIABLE: Final[str] = "A365_DEFENDER_RTP_ENDPOINT"
FAIL_MODE_VARIABLE: Final[str] = "A365_DEFENDER_RTP_FAIL_MODE"
TIMEOUT_VARIABLE: Final[str] = "A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS"
AUTHENTICATION_SCOPE_VARIABLE: Final[str] = "A365_DEFENDER_RTP_AUTHENTICATION_SCOPE"
MAX_CONTENT_CHARACTERS_VARIABLE: Final[str] = "A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS"

_INTEGER = re.compile(r"[+-]?\d+")


@dataclass
class DefenderRtpOptions:
    """Configuration for Microsoft Defender for AI real-time protection.

    Defender RTP is the prevention endpoint ``POST .../v1/protection/evaluate``, which takes
    an agent-hooks/0.1 context and returns a verdict.

    Attributes:
        enabled: Whether Defender real-time protection is enabled (``ENABLE_A365_DEFENDER_RTP``).
        endpoint: The prevention endpoint (``A365_DEFENDER_RTP_ENDPOINT``). Required when enabled.
        authentication_scope: The token scope (``A365_DEFENDER_RTP_AUTHENTICATION_SCOPE``);
            defaults to the Defender API.
        timeout_seconds: Per-call timeout for token acquisition and evaluation, in seconds
            (``A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS``, in milliseconds).
        fail_closed: When true, an evaluation that returns no verdict blocks
            (``A365_DEFENDER_RTP_FAIL_MODE=closed``); otherwise it is allowed and reported as
            not evaluated.
        max_content_characters: Maximum characters per content string sent to Defender
            (``A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS``); all content in one request shares a
            budget of four times that, of which the content under decision (sent twice) may use
            half. The envelope (ids, names, roles) is not cut. When the content under decision
            does not fit, Defender evaluates a truncated copy; its deny still blocks, but its
            allow follows the fail mode.
    """

    DEFENDER_API_APP_ID: ClassVar[str] = DEFENDER_API_APP_ID
    DEFAULT_AUTHENTICATION_SCOPE: ClassVar[str] = DEFAULT_AUTHENTICATION_SCOPE

    enabled: bool = False
    endpoint: str | None = None
    authentication_scope: str = DEFAULT_AUTHENTICATION_SCOPE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    fail_closed: bool = False
    max_content_characters: int = DEFAULT_MAX_CONTENT_CHARACTERS

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> DefenderRtpOptions:
        """Read the options from environment variables.

        Args:
            environ: The variables to read; defaults to ``os.environ``.

        Returns:
            The configured options.

        Raises:
            ValueError: If the endpoint is not an absolute URL, or the timeout or the maximum
                content characters is not a positive integer.
        """
        variables = os.environ if environ is None else environ

        def read(name: str) -> str | None:
            value = variables.get(name)
            if value is None:
                return None
            value = value.strip()
            return value or None

        enabled = read(ENABLE_VARIABLE)
        options = cls(
            enabled=enabled is not None and enabled.lower() in ("true", "1", "yes"),
            fail_closed=(read(FAIL_MODE_VARIABLE) or "").lower() == "closed",
        )

        endpoint = read(ENDPOINT_VARIABLE)
        if endpoint is not None:
            if not is_https_url(endpoint):
                raise ValueError(f"{ENDPOINT_VARIABLE} must be an absolute HTTPS URL.")
            options.endpoint = endpoint

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
        """Raise when the options cannot be used for an enabled client.

        Raises:
            ValueError: If Defender RTP is enabled without an endpoint, the endpoint is not an
                absolute HTTPS URL, or the timeout, the maximum content characters or the
                authentication scope is invalid.
        """
        if self.enabled and not self.endpoint:
            raise ValueError(
                "Defender RTP is enabled but no endpoint is configured. Set "
                f"{ENDPOINT_VARIABLE} or DefenderRtpOptions.endpoint."
            )

        if self.endpoint and not is_https_url(self.endpoint):
            raise ValueError("DefenderRtpOptions.endpoint must be an absolute HTTPS URL.")

        if self.timeout_seconds <= 0:
            raise ValueError("DefenderRtpOptions.timeout_seconds must be positive.")

        if self.max_content_characters <= 0:
            raise ValueError("DefenderRtpOptions.max_content_characters must be positive.")

        if not self.authentication_scope or not self.authentication_scope.strip():
            raise ValueError("DefenderRtpOptions.authentication_scope is required.")


def is_https_url(value: str) -> bool:
    """Whether ``value`` is an absolute HTTPS URL, so tokens never travel in plaintext."""
    parsed = urlparse(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _parse_positive(value: str, name: str) -> int:
    if _INTEGER.fullmatch(value) is not None:
        parsed = int(value)
        if parsed > 0:
            return parsed
    raise ValueError(f"{name} must be a positive integer.")

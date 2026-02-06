# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Utility functions for Microsoft Agent 365 runtime operations.

This module provides utility functions for token handling, agent identity resolution,
and other common runtime operations.
"""

from __future__ import annotations

import os
import platform
import re
import threading
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Optional

import jwt


class Utility:
    """
    Utility class providing common runtime operations for Agent 365.

    This class contains static methods for token processing, agent identity resolution,
    and other utility functions used across the Agent 365 runtime.
    """

    _cached_version: Optional[str] = None
    _cached_application_name: Optional[str] = None
    _application_name_initialized: bool = False
    _cache_lock: threading.Lock = threading.Lock()

    @staticmethod
    def get_app_id_from_token(token: Optional[str]) -> str:
        """
        Decodes the current token and retrieves the App ID (appid or azp claim).

        **WARNING: NO SIGNATURE VERIFICATION** - This method uses jwt.decode() which does NOT
        verify the token signature. The token claims can be spoofed by malicious actors.
        This method is ONLY suitable for logging, analytics, and diagnostics purposes.
        Do NOT use the returned value for authorization, access control, or security decisions.

        Note: Returns a default GUID ('00000000-0000-0000-0000-000000000000') for empty tokens
        for backward compatibility with callers that expect a valid-looking GUID.
        For agent identification where empty string is preferred, use get_agent_id_from_token().

        Args:
            token: JWT token to decode. Can be None or empty.

        Returns:
            str: The App ID from the token's claims, or empty GUID if token is invalid.
                 Returns "00000000-0000-0000-0000-000000000000" if no valid App ID is found.
        """
        if not token or not token.strip():
            return str(uuid.UUID(int=0))

        try:
            # Decode the JWT token without verification (we only need the claims)
            # Note: verify=False is used because we only need to extract claims,
            # not verify the token's authenticity
            decoded_payload = jwt.decode(token, options={"verify_signature": False})

            # Look for appid or azp claims (appid takes precedence)
            app_id = decoded_payload.get("appid") or decoded_payload.get("azp")
            return app_id if app_id else ""

        except (jwt.DecodeError, jwt.InvalidTokenError):
            # Token is malformed or invalid
            return ""

    @staticmethod
    def get_agent_id_from_token(token: Optional[str]) -> str:
        """
        Decodes the token and retrieves the best available agent identifier.
        Checks claims in priority order: xms_par_app_azp (agent blueprint ID) > appid > azp.

        **WARNING: NO SIGNATURE VERIFICATION** - This method uses jwt.decode() which does NOT
        verify the token signature. The token claims can be spoofed by malicious actors.
        This method is ONLY suitable for logging, analytics, and diagnostics purposes.
        Do NOT use the returned value for authorization, access control, or security decisions.

        Note: Returns empty string for empty/missing tokens (unlike get_app_id_from_token() which
        returns a default GUID). This allows callers to omit headers when no identifier is available.

        Args:
            token: JWT token to decode. Can be None or empty.

        Returns:
            str: Agent ID (GUID) or empty string if not found or token is empty.
        """
        if not token or not token.strip():
            return ""

        try:
            decoded_payload = jwt.decode(token, options={"verify_signature": False})

            # Priority: xms_par_app_azp (agent blueprint ID) > appid > azp
            return (
                decoded_payload.get("xms_par_app_azp")
                or decoded_payload.get("appid")
                or decoded_payload.get("azp")
                or ""
            )

        except (jwt.DecodeError, jwt.InvalidTokenError):
            # Silent error handling - return empty string on decode failure
            return ""

    @staticmethod
    def resolve_agent_identity(context: Any, auth_token: Optional[str]) -> str:
        """
        Resolves the agent identity from the turn context or auth token.

        Args:
            context: Turn context of the conversation turn. Expected to have an Activity
                    with methods like is_agentic_request() and get_agentic_instance_id().
            auth_token: Authentication token if available.

        Returns:
            str: The agent identity (App ID). Returns the agentic instance ID if the
                 request is agentic, otherwise returns the App ID from the auth token.
        """
        try:
            # App ID is required to pass to MCP server URL
            # Try to get agentic instance ID if this is an agentic request
            if context and context.activity and context.activity.is_agentic_request():
                agentic_id = context.activity.get_agentic_instance_id()
                return agentic_id if agentic_id else ""

        except (AttributeError, TypeError, Exception):
            # Context/activity doesn't have the expected methods or properties
            # or any other error occurred while accessing context/activity
            pass

        # Fallback to extracting App ID from the auth token
        return Utility.get_app_id_from_token(auth_token)

    @staticmethod
    def get_user_agent_header(orchestrator: Optional[str] = None) -> str:
        """
        Generates a User-Agent header string for SDK requests.

        Args:
            orchestrator: Optional orchestrator name to include in the User-Agent header.
                         Defaults to empty string if not provided.

        Returns:
            str: A formatted User-Agent header string containing SDK version, OS type,
                 Python version, and optional orchestrator information.
        """
        if Utility._cached_version is None:
            try:
                Utility._cached_version = version("microsoft-agents-a365-runtime")
            except PackageNotFoundError:
                Utility._cached_version = "unknown"

        orchestrator_part = f"; {orchestrator}" if orchestrator else ""
        os_type = platform.system()
        python_version = platform.python_version()
        return f"Agent365SDK/{Utility._cached_version} ({os_type}; Python {python_version}{orchestrator_part})"

    @staticmethod
    def get_application_name() -> Optional[str]:
        """
        Gets the application name from environment variable or pyproject.toml.
        The pyproject.toml result is cached at first access to avoid repeated file I/O.

        Returns:
            Optional[str]: Application name or None if not available.
        """
        # First try environment variable (highest priority)
        env_name = os.environ.get("AGENT365_APPLICATION_NAME")
        if env_name:
            return env_name

        # Fall back to cached pyproject.toml name with thread-safe caching
        if not Utility._application_name_initialized:
            with Utility._cache_lock:
                # Double-checked locking pattern
                if not Utility._application_name_initialized:
                    Utility._cached_application_name = (
                        Utility._read_application_name_from_pyproject()
                    )
                    Utility._application_name_initialized = True

        return Utility._cached_application_name

    @staticmethod
    def _read_application_name_from_pyproject() -> Optional[str]:
        """
        Reads the application name from pyproject.toml at the current working directory.

        Note: Uses Path.cwd() which assumes the application is started from its root directory.
        This is a fallback mechanism - AGENT365_APPLICATION_NAME env var is the preferred source.

        Returns:
            Optional[str]: Application name from pyproject.toml or None if not found.
        """
        # Regex pattern to match: name = "value" or name = 'value'
        # This handles exact field name matching and ignores comments
        name_pattern = re.compile(r'^\s*name\s*=\s*["\']([^"\']*)["\']')

        try:
            pyproject_path = Path.cwd() / "pyproject.toml"
            if not pyproject_path.exists():
                return None

            content = pyproject_path.read_text(encoding="utf-8")

            # Simple TOML parsing for [project] name = "..."
            # We avoid importing tomli/tomllib for this simple case
            in_project_section = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "[project]":
                    in_project_section = True
                    continue
                elif stripped.startswith("[") and stripped.endswith("]"):
                    in_project_section = False
                    continue

                if in_project_section:
                    # Use regex to properly parse name = "value" with exact field matching
                    match = name_pattern.match(stripped)
                    if match:
                        value = match.group(1)
                        if value:
                            return value

            return None

        except (OSError, ValueError):
            # File read errors or parsing errors
            return None

    @staticmethod
    def reset_application_name_cache() -> None:
        """
        Resets the cached application name. Used for testing purposes.

        This method is intended for internal testing only.
        """
        Utility._cached_application_name = None
        Utility._application_name_initialized = False

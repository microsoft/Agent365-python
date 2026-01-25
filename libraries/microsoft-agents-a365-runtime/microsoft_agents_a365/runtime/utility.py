# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Utility functions for Microsoft Agent 365 runtime operations.

This module provides utility functions for token handling, agent identity resolution,
and other common runtime operations.
"""

from __future__ import annotations

import platform
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Optional

import jwt


class Utility:
    """
    Utility class providing common runtime operations for Agent 365.

    This class contains static methods for token processing, agent identity resolution,
    and other utility functions used across the Agent 365 runtime.
    """

    _cached_version = None

    @staticmethod
    def get_app_id_from_token(token: Optional[str]) -> str:
        """
        Decodes the current token and retrieves the App ID (appid or azp claim).

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

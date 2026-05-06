# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Provides utility functions for the Tooling components.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.mcp_server_config import MCPServerConfig


# Constants for base URLs
MCP_PLATFORM_PROD_BASE_URL = "https://agent365.svc.cloud.microsoft"

# API endpoint paths
CHAT_HISTORY_ENDPOINT_PATH = "/agents/real-time-threat-protection/chat-message"

PPAPI_TOKEN_SCOPE = "https://api.powerplatform.com"
PROD_MCP_PLATFORM_AUTHENTICATION_SCOPE = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/.default"

# Shared ATG AppId — V1 servers (no audience field) use this scope
ATG_APP_ID = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1"
# ATG AppId in Application ID URI form — also treated as V1
ATG_APP_ID_URI = f"api://{ATG_APP_ID}"


def get_tooling_gateway_for_digital_worker(agentic_app_id: str) -> str:
    """
    Gets the tooling gateway URL for the specified digital worker.

    Args:
        agentic_app_id: The agentic app identifier of the digital worker.

    Returns:
        str: The tooling gateway URL for the digital worker.
    """
    # The endpoint needs to be updated based on the environment (prod, dev, etc.)
    return f"{_get_mcp_platform_base_url()}/agents/v2/{agentic_app_id}/mcpServers"


def get_mcp_base_url() -> str:
    """
    Gets the base URL for MCP servers.

    Returns:
        str: The base URL for MCP servers.
    """
    return f"{_get_mcp_platform_base_url()}/agents/servers"


def build_mcp_server_url(server_name: str) -> str:
    """
    Constructs the full MCP server URL using the base URL and server name.

    Args:
        server_name: The MCP server name.

    Returns:
        str: The full MCP server URL.
    """
    base_url = get_mcp_base_url()

    return f"{base_url}/{server_name}"


def is_development_environment() -> bool:
    """
    Returns True if the current environment is configured as development.

    Resolution order (first non-empty value wins):
    1. ``PYTHON_ENVIRONMENT``     — explicit Python SDK variable used in current samples.
    2. ``ENVIRONMENT``            — legacy Python SDK variable (backward compatibility).
    3. ``ASPNETCORE_ENVIRONMENT`` — Azure hosting convention.
    4. ``DOTNET_ENVIRONMENT``     — generic-host convention.
    5. Defaults to ``"Development"`` when none of the above are set.

    ``PYTHON_ENVIRONMENT`` and ``ENVIRONMENT`` are checked first so that agents
    which explicitly set ``ENVIRONMENT=Production`` are not affected if a host
    process also sets ``ASPNETCORE_ENVIRONMENT``.

    Returns:
        bool: True when the resolved environment is "development" (case-insensitive).
    """
    environment = (
        os.getenv("PYTHON_ENVIRONMENT")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ASPNETCORE_ENVIRONMENT")
        or os.getenv("DOTNET_ENVIRONMENT")
        or "Development"
    )
    return environment.lower() == "development"


def _get_current_environment() -> str:
    """
    Gets the current environment name.

    Returns:
        str: The current environment name.
    """
    return os.getenv("ASPNETCORE_ENVIRONMENT") or os.getenv("DOTNET_ENVIRONMENT") or "Development"


def _get_mcp_platform_base_url() -> str:
    """
    Gets the base URL for MCP platform, defaults to production URL if not set.

    Returns:
        str: The base URL for MCP platform.
    """
    endpoint = os.getenv("MCP_PLATFORM_ENDPOINT")
    if endpoint is not None:
        return endpoint

    return MCP_PLATFORM_PROD_BASE_URL


def get_mcp_platform_authentication_scope() -> list[str]:
    """
    Gets the MCP platform authentication scope.

    Returns:
        list[str]: A list containing the appropriate MCP platform authentication scope.
    """
    env_scope = os.getenv("MCP_PLATFORM_AUTHENTICATION_SCOPE", "")

    if env_scope:
        return [env_scope]

    return [PROD_MCP_PLATFORM_AUTHENTICATION_SCOPE]


def get_chat_history_endpoint() -> str:
    """
    Gets the chat history endpoint URL for sending chat history to the MCP platform.

    Returns:
        str: The chat history endpoint URL.
    """
    return f"{_get_mcp_platform_base_url()}{CHAT_HISTORY_ENDPOINT_PATH}"


def resolve_token_scope_for_server(server: MCPServerConfig) -> str:
    """
    Resolve the OAuth scope to request for a given MCP server.

    V2 servers carry their own audience in the ``audience`` field (bare GUID or
    ``api://`` URI form). When an explicit ``scope`` is provided (e.g.
    ``"Tools.ListInvoke.All"``), the scope is ``{audience}/{scope}``. When scope
    is absent, ``{audience}/.default`` is used (relies on pre-consented scopes).
    V1 servers (no audience, audience equals the shared ATG AppId in bare GUID or
    ``api://`` URI form) always fall back to the shared ATG ``/.default`` scope.

    Args:
        server: The MCP server configuration to resolve the scope for.

    Returns:
        str: The OAuth scope string, e.g. ``"<guid>/Tools.ListInvoke.All"``,
        ``"api://<guid>/.default"``, or the shared ATG ``"<atg-guid>/.default"``.
    """
    if server.audience is not None:
        # Normalize once: strip whitespace and lowercase so that GUID casing differences
        # (e.g. "EA9FFC3E-..." vs "ea9ffc3e-...") and api:// scheme variations do not
        # misclassify V1 servers as V2 or produce inconsistent OAuth cache keys.
        audience = server.audience.strip().lower()
        if (
            audience != "default"
            and audience != ATG_APP_ID  # already lowercase constant
            and audience != ATG_APP_ID_URI  # already lowercase constant
        ):
            # V2: use explicit scope when present, fall back to /.default (pre-consented).
            # Use the normalized audience so scope strings are consistent cache keys.
            if server.scope:
                return f"{audience}/{server.scope}"
            return f"{audience}/.default"
    # V1: shared ATG platform token, configurable via MCP_PLATFORM_AUTHENTICATION_SCOPE env var
    return get_mcp_platform_authentication_scope()[0]

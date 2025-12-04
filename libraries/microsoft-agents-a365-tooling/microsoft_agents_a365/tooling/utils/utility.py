# Copyright (c) Microsoft. All rights reserved.

"""
Provides utility functions for the Tooling components.
"""

import os


# Constants for base URLs
MCP_PLATFORM_PROD_BASE_URL = "https://agent365.svc.cloud.microsoft"

PPAPI_TOKEN_SCOPE = "https://api.powerplatform.com"
PROD_MCP_PLATFORM_AUTHENTICATION_SCOPE = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/.default"


def get_tooling_gateway_for_digital_worker(agentic_app_id: str) -> str:
    """
    Gets the tooling gateway URL for the specified digital worker.

    Args:
        agentic_app_id: The agentic app identifier of the digital worker.

    Returns:
        str: The tooling gateway URL for the digital worker.
    """
    # The endpoint needs to be updated based on the environment (prod, dev, etc.)
    return f"{_get_mcp_platform_base_url()}/agents/{agentic_app_id}/mcpServers"


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
    if os.getenv("MCP_PLATFORM_ENDPOINT") is not None:
        return os.getenv("MCP_PLATFORM_ENDPOINT")

    return MCP_PLATFORM_PROD_BASE_URL


def get_mcp_platform_authentication_scope():
    """
    Gets the MCP platform authentication scope.

    Returns:
        list: A list containing the appropriate MCP platform authentication scope.
    """
    envScope = os.getenv("MCP_PLATFORM_AUTHENTICATION_SCOPE", "")

    if envScope:
        return [envScope]

    return [PROD_MCP_PLATFORM_AUTHENTICATION_SCOPE]

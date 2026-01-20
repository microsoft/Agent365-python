# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Provides utility functions for the Tooling components.
"""

import os


# Constants for base URLs
MCP_PLATFORM_PROD_BASE_URL = "https://agent365.svc.cloud.microsoft"

# API endpoint paths
CHAT_HISTORY_ENDPOINT_PATH = "/agents/real-time-threat-protection/chat-message"

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

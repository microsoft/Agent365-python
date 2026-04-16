# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service for Google ADK.

This service provides MCP (Model Context Protocol) tool registration
capabilities for Google ADK-based agents.
"""

# Standard library imports
import logging
from typing import List, Optional

# Third-party imports
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

# Local imports
from microsoft_agents.hosting.core import Authorization, TurnContext
from microsoft_agents_a365.runtime.utility import Utility
from microsoft_agents_a365.tooling.models import ToolOptions
from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
    McpToolServerConfigurationService,
)
from microsoft_agents_a365.tooling.utils.constants import Constants
from microsoft_agents_a365.tooling.utils.utility import (
    get_mcp_platform_authentication_scope,
    is_development_environment,
)


class McpToolRegistrationService:
    """
    Provides MCP tool registration services for Google ADK agents.

    This service handles registration and management of MCP (Model Context Protocol)
    tool servers with Google ADK agents.
    """

    _orchestrator_name: str = "GoogleADK"

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MCP Tool Registration Service for Google ADK.

        Args:
            logger: Logger instance for logging operations.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._mcp_server_configuration_service = McpToolServerConfigurationService(
            logger=self._logger
        )
        self._connected_servers: List[McpToolset] = []

    async def add_tool_servers_to_agent(
        self,
        agent: Agent,
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
        auth_token: Optional[str] = None,
    ) -> None:
        """
        Add new MCP servers to the agent from MCP Platform.

        Note: Modifies the provided agent in place to add new MCP tool servers.

        Args:
            agent: The existing agent to add servers to.
            auth: Authorization object used to exchange tokens for MCP server access.
            auth_handler_name: Name of the authorization handler.
            context: TurnContext object representing the current turn/session context.
            auth_token: Authentication token to access the MCP servers.
                       If not provided, will be obtained using `auth` and `context`.

        Returns:
            None
        """
        is_dev = is_development_environment()
        if not auth_token and not is_dev:
            # Only exchange a token in production; dev mode uses BEARER_TOKEN* env vars instead.
            scopes = get_mcp_platform_authentication_scope()
            auth_token_obj = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = auth_token_obj.token

        # In dev mode, agentic_app_id is not needed for manifest-based discovery.
        agentic_app_id = "" if is_dev else Utility.resolve_agent_identity(context, auth_token)
        self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        mcp_server_configs = await self._mcp_server_configuration_service.list_tool_servers(
            agentic_app_id=agentic_app_id,
            auth_token=auth_token,
            options=options,
            authorization=auth,
            auth_handler_name=auth_handler_name,
            turn_context=context,
        )

        self._logger.info(f"Loaded {len(mcp_server_configs)} MCP server configurations")

        # Collect existing server URLs to prevent duplicates (use set for O(1) lookup)
        existing_server_urls = set()
        for tool in agent.tools:
            # Check if the tool is an McpToolset and has a connection_params.url
            if hasattr(tool, "connection_params") and hasattr(tool.connection_params, "url"):
                existing_server_urls.add(tool.connection_params.url)

        self._logger.debug(f"Found {len(existing_server_urls)} existing MCP servers in agent")

        # Convert MCP server configs to McpToolset objects (only new ones)
        mcp_servers_info = []

        for server_config in mcp_server_configs:
            # Skip if server URL already exists
            if server_config.url in existing_server_urls:
                self._logger.debug(
                    f"Skipping MCP server '{server_config.mcp_server_name}' "
                    f"at {server_config.url} - already exists in agent"
                )
                continue

            try:
                base_headers = {
                    Constants.Headers.USER_AGENT: Utility.get_user_agent_header(
                        self._orchestrator_name
                    )
                }
                server_headers = dict(server_config.headers) if server_config.headers else {}
                # Fall back to the shared discovery token when no per-server
                # Authorization header was attached (e.g. dev mode without
                # BEARER_TOKEN* env vars, or legacy V1 callers).
                if Constants.Headers.AUTHORIZATION not in server_headers and auth_token:
                    server_headers[Constants.Headers.AUTHORIZATION] = (
                        auth_token
                        if auth_token.lower().startswith(
                            f"{Constants.Headers.BEARER_PREFIX.lower()} "
                        )
                        else f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
                    )
                headers = {**base_headers, **server_headers}  # per-audience token takes precedence

                server_info = McpToolset(
                    connection_params=StreamableHTTPConnectionParams(
                        url=server_config.url,
                        headers=headers,
                    )
                )

                mcp_servers_info.append(server_info)
                self._connected_servers.append(server_info)
                existing_server_urls.add(server_config.url)
                self._logger.info(
                    f"Created MCP toolset for '{server_config.mcp_server_name}' "
                    f"at {server_config.url}"
                )

            except (ConnectionError, TimeoutError, ValueError) as tool_ex:
                # Expected connection/configuration errors
                self._logger.warning(
                    f"Failed to create MCP toolset for '{server_config.mcp_server_name}': {tool_ex}"
                )
                continue
            except Exception as tool_ex:
                # Unexpected errors - log at ERROR level with full traceback
                self._logger.error(
                    f"Unexpected error creating MCP toolset for '{server_config.mcp_server_name}': {tool_ex}",
                    exc_info=True,
                )
                continue

        # Only modify agent.tools if we have new servers to add
        if mcp_servers_info:
            all_tools = list(agent.tools) + mcp_servers_info
            agent.tools = all_tools
            self._logger.info(
                f"Successfully configured agent with {len(mcp_servers_info)} new MCP tool servers "
                f"(total tools: {len(all_tools)})"
            )
        else:
            self._logger.info("No new MCP servers to add to agent")

    async def cleanup(self):
        """Clean up any resources used by the service."""
        try:
            for toolset in self._connected_servers:
                try:
                    if hasattr(toolset, "close"):
                        await toolset.close()
                except Exception as cleanup_ex:
                    self._logger.debug(f"Error during cleanup: {cleanup_ex}")
            self._connected_servers.clear()
        except Exception as ex:
            self._logger.debug(f"Error during service cleanup: {ex}")

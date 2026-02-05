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
        self.config_service = McpToolServerConfigurationService(logger=self._logger)
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
        if not auth_token:
            scopes = get_mcp_platform_authentication_scope()
            auth_token_obj = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = auth_token_obj.token

        agentic_app_id = Utility.resolve_agent_identity(context, auth_token)
        self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        mcp_server_configs = await self.config_service.list_tool_servers(
            agentic_app_id=agentic_app_id,
            auth_token=auth_token,
            options=options,
        )

        self._logger.info(f"Loaded {len(mcp_server_configs)} MCP server configurations")

        # Convert MCP server configs to McpToolset objects
        mcp_servers_info = []
        mcp_server_headers = {
            Constants.Headers.AUTHORIZATION: f"{Constants.Headers.BEARER_PREFIX} {auth_token}",
            Constants.Headers.USER_AGENT: Utility.get_user_agent_header(self._orchestrator_name),
        }

        for server_config in mcp_server_configs:
            try:
                server_info = McpToolset(
                    connection_params=StreamableHTTPConnectionParams(
                        url=server_config.mcp_server_unique_name,
                        headers=mcp_server_headers,
                    )
                )

                mcp_servers_info.append(server_info)
                self._connected_servers.append(server_info)
                self._logger.info(
                    f"Created MCP toolset for '{server_config.mcp_server_name}' "
                    f"at {server_config.mcp_server_unique_name}"
                )

            except Exception as tool_ex:
                server_name = getattr(server_config, "mcp_server_name", "Unknown")
                self._logger.warning(f"Failed to create MCP toolset for {server_name}: {tool_ex}")
                continue

        # Combine existing tools with new MCP servers
        all_tools = list(agent.tools) + mcp_servers_info

        self._logger.info(
            f"Successfully configured agent with {len(mcp_servers_info)} MCP tool servers "
            f"(total tools: {len(all_tools)})"
        )

        agent.tools = all_tools

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

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Dict, Optional
from dataclasses import dataclass
import logging

from agents import Agent

from microsoft_agents.hosting.core import Authorization, TurnContext

from agents.mcp import (
    MCPServerStreamableHttp,
    MCPServerStreamableHttpParams,
)
from microsoft_agents_a365.runtime.utility import Utility
from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
    McpToolServerConfigurationService,
)

from microsoft_agents_a365.tooling.models import ToolOptions
from microsoft_agents_a365.tooling.utils.constants import Constants
from microsoft_agents_a365.tooling.utils.utility import (
    get_mcp_platform_authentication_scope,
)


# TODO: This is not needed. Remove this.
@dataclass
class MCPServerInfo:
    """Information about an MCP server"""

    name: str
    url: str
    server_type: str = "streamable_http"  # hosted, streamable_http, sse, stdio
    headers: Optional[Dict[str, str]] = None
    require_approval: str = "never"
    timeout: int = 30  # Timeout in seconds (will be converted to milliseconds for MCPServerStreamableHttpParams)


class McpToolRegistrationService:
    """Service for managing MCP tools and servers for an agent"""

    _orchestrator_name: str = "OpenAI"

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MCP Tool Registration Service for OpenAI.

        Args:
            logger: Logger instance for logging operations.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.config_service = McpToolServerConfigurationService(logger=self._logger)

    async def add_tool_servers_to_agent(
        self,
        agent: Agent,
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
        auth_token: Optional[str] = None,
    ):
        """
        Add new MCP servers to the agent by creating a new Agent instance.

        Note: Due to OpenAI Agents SDK limitations, MCP servers must be set during
        Agent creation. If new servers are found, this method creates a new Agent
        instance with all MCP servers (existing + new) properly initialized.

        Args:
            agent: The existing agent to add servers to
            auth: Authorization handler for token exchange.
            auth_handler_name: Name of the authorization handler.
            context: Turn context for the current operation.
            auth_token: Authentication token to access the MCP servers.

        Returns:
            New Agent instance with all MCP servers, or original agent if no new servers
        """

        if not auth_token:
            scopes = get_mcp_platform_authentication_scope()
            authToken = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = authToken.token

        # Get MCP server configurations from the configuration service
        # mcp_server_configs = []
        # TODO: radevika: Update once the common project is merged.

        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        agentic_app_id = Utility.resolve_agent_identity(context, auth_token)
        self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")
        mcp_server_configs = await self.config_service.list_tool_servers(
            agentic_app_id=agentic_app_id,
            auth_token=auth_token,
            options=options,
        )

        self._logger.info(f"Loaded {len(mcp_server_configs)} MCP server configurations")

        # Convert MCP server configs to MCPServerInfo objects
        mcp_servers_info = []
        for server_config in mcp_server_configs:
            server_info = MCPServerInfo(
                name=server_config.mcp_server_name,
                url=server_config.mcp_server_unique_name,
            )
            mcp_servers_info.append(server_info)

        # Get existing MCP servers from the agent
        existing_mcp_servers = (
            list(agent.mcp_servers) if hasattr(agent, "mcp_servers") and agent.mcp_servers else []
        )

        # Prepare new MCP servers to add
        new_mcp_servers = []
        connected_servers = []

        existing_server_urls = []
        for server in existing_mcp_servers:
            # Check for URL in params dict (MCPServerStreamableHttp stores URL in params["url"])
            if (
                hasattr(server, "params")
                and isinstance(server.params, dict)
                and "url" in server.params
            ):
                existing_server_urls.append(server.params["url"])
            elif hasattr(server, "params") and hasattr(server.params, "url"):
                existing_server_urls.append(server.params.url)
            elif hasattr(server, "url"):
                existing_server_urls.append(server.url)

        for si in mcp_servers_info:
            # Check if MCP server already exists

            if si.url not in existing_server_urls:
                try:
                    # Prepare headers with authorization
                    headers = si.headers or {}
                    if auth_token:
                        headers[Constants.Headers.AUTHORIZATION] = (
                            f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
                        )

                    headers[Constants.Headers.USER_AGENT] = Utility.get_user_agent_header(
                        self._orchestrator_name
                    )

                    # Create MCPServerStreamableHttpParams with proper configuration
                    params = MCPServerStreamableHttpParams(url=si.url, headers=headers)

                    # Create MCP server
                    mcp_server = MCPServerStreamableHttp(params=params, name=si.name)

                    # CRITICAL: Connect the server before adding it to the agent
                    # This fixes the "Server not initialized. Make sure you call `connect()` first." error
                    # TODO: When App Manifest scenario lits up for onboarding agent, we need to pull a flag and disconnect if the flag is disabled.
                    await mcp_server.connect()

                    new_mcp_servers.append(mcp_server)
                    connected_servers.append(mcp_server)

                    existing_server_urls.append(si.url)
                    self._logger.info(
                        f"Successfully connected to MCP server '{si.name}' at {si.url}"
                    )

                except Exception as e:
                    # Log the error but continue with other servers
                    self._logger.warning(
                        f"Failed to connect to MCP server {si.name} at {si.url}: {e}"
                    )
                    continue

        # If we have new servers, we need to recreate the agent
        # The OpenAI Agents SDK requires MCP servers to be set during agent creation
        if new_mcp_servers:
            try:
                self._logger.info(f"Recreating agent with {len(new_mcp_servers)} new MCP servers")
                all_mcp_servers = existing_mcp_servers + new_mcp_servers

                # Recreate the agent with all MCP servers
                from agents import Agent

                new_agent = Agent(
                    name=agent.name,
                    model=agent.model,
                    model_settings=agent.model_settings
                    if hasattr(agent, "model_settings")
                    else None,
                    instructions=agent.instructions,
                    tools=agent.tools,
                    mcp_servers=all_mcp_servers,
                )

                # Copy agent attributes to preserve state
                for attr_name in ["name", "model", "instructions", "tools"]:
                    if hasattr(agent, attr_name):
                        setattr(new_agent, attr_name, getattr(agent, attr_name))

                # Store connected servers for potential cleanup
                if not hasattr(self, "_connected_servers"):
                    self._connected_servers = []
                self._connected_servers.extend(connected_servers)

                self._logger.info(
                    f"Agent recreated successfully with {len(all_mcp_servers)} total MCP servers"
                )
                # Return the new agent (caller needs to replace the old one)
                return new_agent

            except Exception as e:
                # Clean up connected servers if agent creation fails
                self._logger.error(f"Failed to recreate agent with new MCP servers: {e}")
                await self._cleanup_servers(connected_servers)
                raise e

        self._logger.info("No new MCP servers to add to agent")
        return agent

    async def _cleanup_servers(self, servers):
        """Clean up connected MCP servers"""
        for server in servers:
            try:
                if hasattr(server, "cleanup"):
                    await server.cleanup()
            except Exception as e:
                # Log cleanup errors but don't raise them
                self._logger.debug(f"Error during server cleanup: {e}")

    async def cleanup_all_servers(self):
        """Clean up all connected MCP servers"""
        if hasattr(self, "_connected_servers"):
            await self._cleanup_servers(self._connected_servers)
            self._connected_servers = []

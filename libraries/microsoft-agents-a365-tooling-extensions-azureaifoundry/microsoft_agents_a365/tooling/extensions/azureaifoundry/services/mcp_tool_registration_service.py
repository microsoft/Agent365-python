# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service implementation for Azure Foundry.

This module provides the concrete implementation of the MCP (Model Context Protocol)
tool registration service that integrates with Azure Foundry to add MCP tool
servers to agents.
"""

# Standard library imports
import logging
from typing import List, Optional, Sequence, Tuple

# Third-party imports - Azure AI
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import McpTool, ThreadMessage, ToolResources
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from microsoft_agents.hosting.core import Authorization, TurnContext

from microsoft_agents_a365.runtime import OperationError, OperationResult
from microsoft_agents_a365.runtime.utility import Utility
from microsoft_agents_a365.tooling.models import ChatHistoryMessage, ToolOptions
from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
    McpToolServerConfigurationService,
)
from microsoft_agents_a365.tooling.utils.constants import Constants
from microsoft_agents_a365.tooling.utils.utility import get_mcp_platform_authentication_scope


class McpToolRegistrationService:
    """
    Provides MCP tool registration services for Azure Foundry agents.

    This service handles registration and management of MCP (Model Context Protocol)
    tool servers with Azure Foundry agents using the Azure AI SDK. It provides
    seamless integration between MCP servers and Azure Foundry's agent framework.

    Features:
    - Automatic MCP server discovery and configuration
    - Azure identity integration with DefaultAzureCredential
    - Tool definitions and resources management
    - Support for both development (ToolingManifest.json) and production (gateway API) scenarios
    - Comprehensive error handling and logging

    Example:
        >>> service = McpToolRegistrationService()
        >>> service.add_tool_servers_to_agent(project_client, agent_id, token)
    """

    _orchestrator_name: str = "AzureAIFoundry"

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        credential: Optional["DefaultAzureCredential"] = None,
    ):
        """
        Initialize the MCP Tool Registration Service for Azure Foundry.

        Args:
            logger: Logger instance for logging operations.
            credential: Azure credential for authentication. If None, DefaultAzureCredential will be used.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._credential = credential or DefaultAzureCredential()
        self._mcp_server_configuration_service = McpToolServerConfigurationService(
            logger=self._logger
        )

    # ============================================================================
    # Public Methods - Main Entry Points
    # ============================================================================

    async def add_tool_servers_to_agent(
        self,
        project_client: "AIProjectClient",
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
        auth_token: Optional[str] = None,
    ) -> None:
        """
        Adds MCP tool servers to an Azure Foundry agent.

        Args:
            project_client: The Azure Foundry AIProjectClient instance.
            auth: Authorization handler for token exchange.
            auth_handler_name: Name of the authorization handler.
            context: Turn context for the current operation.
            auth_token: Authentication token to access the MCP servers.

        Raises:
            ValueError: If project_client is None or required parameters are invalid.
            Exception: If there's an error during MCP tool registration.
        """
        if project_client is None:
            raise ValueError("project_client cannot be None")

        if not auth_token:
            scopes = get_mcp_platform_authentication_scope()
            authToken = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = authToken.token

        try:
            agentic_app_id = Utility.resolve_agent_identity(context, auth_token)
            # Get the tool definitions and resources using the async implementation
            tool_definitions, tool_resources = await self._get_mcp_tool_definitions_and_resources(
                agentic_app_id, auth_token or ""
            )

            # Update the agent with the tools
            project_client.agents.update_agent(
                agentic_app_id, tools=tool_definitions, tool_resources=tool_resources
            )

            self._logger.info(
                f"Successfully configured {len(tool_definitions)} MCP tool servers for agent"
            )

        except Exception as ex:
            self._logger.error(
                f"Unhandled failure during MCP tool registration workflow for agent user {agentic_app_id}: {ex}"
            )
            raise

    async def _get_mcp_tool_definitions_and_resources(
        self, agentic_app_id: str, auth_token: str
    ) -> Tuple[List[McpTool], Optional[ToolResources]]:
        """
        Internal method to get MCP tool definitions and resources.

        This implements the core logic equivalent to the C# method of the same name.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            auth_token: Authentication token to access the MCP servers.

        Returns:
            Tuple containing tool definitions and resources.
        """
        if self._mcp_server_configuration_service is None:
            self._logger.error("MCP server configuration service is not available")
            return ([], None)

        # Get MCP server configurations
        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        try:
            servers = await self._mcp_server_configuration_service.list_tool_servers(
                agentic_app_id, auth_token, options
            )
        except Exception as ex:
            self._logger.error(
                f"Failed to list MCP tool servers for AgenticAppId={agentic_app_id}: {ex}"
            )
            return ([], None)

        if len(servers) == 0:
            self._logger.info(f"No MCP servers configured for AgenticAppId={agentic_app_id}")
            return ([], None)

        # Collections to build for the return value
        tool_definitions: List[McpTool] = []
        combined_tool_resources = ToolResources()

        for server in servers:
            # Validate server configuration
            if not server.mcp_server_name or not server.mcp_server_unique_name:
                self._logger.warning(
                    f"Skipping invalid MCP server config: Name='{server.mcp_server_name}', Url='{server.mcp_server_unique_name}'"
                )
                continue

            # TODO: The Foundry SDK currently allows MCP label names without the "mcp_" prefix,
            # which is unintended and has been identified as a bug.
            # This change should be reverted once the official fix is availab
            server_label = (
                server.mcp_server_name[4:]
                if server.mcp_server_name.lower().startswith("mcp_")
                else server.mcp_server_name
            )

            # Use the URL from server (always populated by the configuration service)
            server_url = server.url

            # Create MCP tool using Azure Foundry SDK
            mcp_tool = McpTool(server_label=server_label, server_url=server_url)

            # Configure the tool
            mcp_tool.set_approval_mode("never")

            # Set up authorization header
            if auth_token:
                header_value = (
                    auth_token
                    if auth_token.lower().startswith(f"{Constants.Headers.BEARER_PREFIX.lower()} ")
                    else f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
                )
                mcp_tool.update_headers(Constants.Headers.AUTHORIZATION, header_value)

            mcp_tool.update_headers(
                Constants.Headers.USER_AGENT, Utility.get_user_agent_header(self._orchestrator_name)
            )

            # Add to collections
            tool_definitions.extend(mcp_tool.definitions)
            if mcp_tool.resources and mcp_tool.resources.mcp:
                if combined_tool_resources.mcp is None:
                    combined_tool_resources.mcp = []
                combined_tool_resources.mcp.extend(mcp_tool.resources.mcp)

        # Return None if no servers were processed successfully
        if combined_tool_resources.mcp is None or len(combined_tool_resources.mcp) == 0:
            combined_tool_resources = None

        self._logger.info(
            f"Processed {len(servers)} MCP servers, created {len(tool_definitions)} tool definitions"
        )

        return (tool_definitions, combined_tool_resources)

    # ============================================================================
    # Public Methods - Chat History API
    # ============================================================================

    async def send_chat_history_messages(
        self,
        turn_context: TurnContext,
        messages: Sequence[ThreadMessage],
        tool_options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send Azure AI Foundry chat history messages to the MCP platform.

        This method accepts a sequence of Azure AI Foundry ThreadMessage objects,
        converts them to ChatHistoryMessage format, and sends them to the MCP
        platform for real-time threat protection.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation info.
            messages: Sequence of Azure AI Foundry ThreadMessage objects to send.
            tool_options: Optional configuration for the request.

        Returns:
            OperationResult indicating success or failure.

        Raises:
            ValueError: If turn_context or messages is None.

        Example:
            >>> service = McpToolRegistrationService()
            >>> messages = await agents_client.messages.list(thread_id=thread_id)
            >>> result = await service.send_chat_history_messages(
            ...     turn_context, list(messages)
            ... )
            >>> if result.succeeded:
            ...     print("Chat history sent successfully")
        """
        # Input validation
        if turn_context is None:
            raise ValueError("turn_context cannot be None")
        if messages is None:
            raise ValueError("messages cannot be None")

        self._logger.info(f"Sending {len(messages)} Azure AI Foundry messages as chat history")

        # Set default options with orchestrator name
        if tool_options is None:
            tool_options = ToolOptions(orchestrator_name=self._orchestrator_name)
        elif tool_options.orchestrator_name is None:
            tool_options.orchestrator_name = self._orchestrator_name

        try:
            # Convert ThreadMessage objects to ChatHistoryMessage format
            chat_history_messages = self._convert_thread_messages_to_chat_history(messages)

            self._logger.debug(
                f"Converted {len(chat_history_messages)} messages to ChatHistoryMessage format"
            )

            # Delegate to core service
            result = await self._mcp_server_configuration_service.send_chat_history(
                turn_context=turn_context,
                chat_history_messages=chat_history_messages,
                options=tool_options,
            )

            if result.succeeded:
                self._logger.info(
                    f"Chat history sent successfully with {len(chat_history_messages)} messages"
                )
            else:
                self._logger.error(f"Failed to send chat history: {result}")

            return result

        except ValueError:
            # Re-raise validation errors from the core service
            raise
        except Exception as ex:
            self._logger.error(f"Failed to send chat history messages: {ex}")
            return OperationResult.failed(OperationError(ex))

    async def send_chat_history(
        self,
        agents_client: AgentsClient,
        thread_id: str,
        turn_context: TurnContext,
        tool_options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Retrieve and send chat history from Azure AI Foundry to the MCP platform.

        This method retrieves messages from the Azure AI Foundry Agents API using
        the provided client and thread ID, converts them to ChatHistoryMessage
        format, and sends them to the MCP platform.

        Args:
            agents_client: The Azure AI Foundry AgentsClient instance.
            thread_id: The thread ID containing the messages to send.
            turn_context: TurnContext from the Agents SDK containing conversation info.
            tool_options: Optional configuration for the request.

        Returns:
            OperationResult indicating success or failure.

        Raises:
            ValueError: If agents_client, thread_id, or turn_context is None/empty.

        Example:
            >>> from azure.ai.agents import AgentsClient
            >>> from azure.identity import DefaultAzureCredential
            >>>
            >>> client = AgentsClient(endpoint, credential=DefaultAzureCredential())
            >>> service = McpToolRegistrationService()
            >>> result = await service.send_chat_history(
            ...     client, thread_id, turn_context
            ... )
        """
        # Input validation
        if agents_client is None:
            raise ValueError("agents_client cannot be None")
        if thread_id is None or not thread_id.strip():
            raise ValueError("thread_id cannot be empty")
        if turn_context is None:
            raise ValueError("turn_context cannot be None")

        try:
            # Retrieve messages from the thread
            messages: List[ThreadMessage] = []
            async for message in agents_client.messages.list(thread_id=thread_id):
                messages.append(message)

            self._logger.info(f"Retrieved {len(messages)} messages from thread {thread_id}")

            # Delegate to send_chat_history_messages
            return await self.send_chat_history_messages(
                turn_context=turn_context,
                messages=messages,
                tool_options=tool_options,
            )

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as ex:
            self._logger.error(f"Failed to send chat history from thread {thread_id}: {ex}")
            return OperationResult.failed(OperationError(ex))

    # ============================================================================
    # Private Methods - Message Conversion Helpers
    # ============================================================================

    def _convert_thread_messages_to_chat_history(
        self,
        messages: Sequence[ThreadMessage],
    ) -> List[ChatHistoryMessage]:
        """
        Convert Azure AI Foundry ThreadMessage objects to ChatHistoryMessage format.

        This internal helper method transforms Azure AI Foundry's native ThreadMessage
        objects into the ChatHistoryMessage format expected by the MCP platform's
        real-time threat protection endpoint.

        Args:
            messages: Sequence of ThreadMessage objects to convert.

        Returns:
            List of ChatHistoryMessage objects ready for the MCP platform.

        Note:
            - Messages with None id, None role, or empty content are filtered out
            - Role is extracted via the .value property of the MessageRole enum
            - Timestamp is taken from message.created_at
        """
        history_messages: List[ChatHistoryMessage] = []

        for message in messages:
            # Skip None messages
            if message is None:
                self._logger.warning("Skipping null message")
                continue

            # Skip messages with None id
            if message.id is None:
                self._logger.warning("Skipping message with null ID")
                continue

            # Skip messages with None role
            if message.role is None:
                self._logger.warning(f"Skipping message with null role (ID: {message.id})")
                continue

            # Extract content from message
            content = self._extract_content_from_message(message)

            # Skip messages with empty content
            if not content or not content.strip():
                self._logger.warning(f"Skipping message {message.id} with empty content")
                continue

            # Convert role enum to lowercase string
            role_value = message.role.value if hasattr(message.role, "value") else str(message.role)
            role = role_value.lower()

            # Create ChatHistoryMessage
            history_message = ChatHistoryMessage(
                id=message.id,
                role=role,
                content=content,
                timestamp=message.created_at,
            )
            history_messages.append(history_message)

            self._logger.debug(
                f"Converted message {message.id} with role '{role}' to ChatHistoryMessage"
            )

        if len(history_messages) == 0 and len(messages) > 0:
            self._logger.warning("All messages were filtered out during conversion")

        return history_messages

    def _extract_content_from_message(self, message: ThreadMessage) -> str:
        """
        Extract text content from a ThreadMessage's content items.

        This method iterates through the message's content list and extracts
        text from MessageTextContent items, concatenating them with spaces.

        Args:
            message: Azure AI Foundry ThreadMessage object.

        Returns:
            Concatenated text content as string, or empty string if no text found.
        """
        if message.content is None or len(message.content) == 0:
            return ""

        text_parts: List[str] = []

        for content_item in message.content:
            # Check for MessageTextContent by duck typing (has text attribute with value)
            # This handles both real SDK types and mock objects in tests
            if hasattr(content_item, "text") and content_item.text is not None:
                text_value = getattr(content_item.text, "value", None)
                if text_value is not None and text_value:
                    text_parts.append(text_value)

        return " ".join(text_parts)

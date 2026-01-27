# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence, Union

from agent_framework import ChatAgent, ChatMessage, ChatMessageStoreProtocol, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.openai import OpenAIChatClient

from microsoft_agents.hosting.core import Authorization, TurnContext

from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.runtime.utility import Utility
from microsoft_agents_a365.tooling.models import ChatHistoryMessage, ToolOptions
from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
    McpToolServerConfigurationService,
)
from microsoft_agents_a365.tooling.utils.constants import Constants
from microsoft_agents_a365.tooling.utils.utility import (
    get_mcp_platform_authentication_scope,
)


class McpToolRegistrationService:
    """
    Provides MCP tool registration services for Agent Framework agents.

    This service handles registration and management of MCP (Model Context Protocol)
    tool servers with Agent Framework agents.
    """

    _orchestrator_name: str = "AgentFramework"

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MCP Tool Registration Service for Agent Framework.

        Args:
            logger: Logger instance for logging operations.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._mcp_server_configuration_service = McpToolServerConfigurationService(
            logger=self._logger
        )
        self._connected_servers = []

    async def add_tool_servers_to_agent(
        self,
        chat_client: Union[OpenAIChatClient, AzureOpenAIChatClient],
        agent_instructions: str,
        initial_tools: List[Any],
        auth: Authorization,
        auth_handler_name: str,
        turn_context: TurnContext,
        auth_token: Optional[str] = None,
    ) -> Optional[ChatAgent]:
        """
        Add MCP tool servers to a chat agent (mirrors .NET implementation).

        Args:
            chat_client: The chat client instance (Union[OpenAIChatClient, AzureOpenAIChatClient])
            agent_instructions: Instructions for the agent behavior
            initial_tools: List of initial tools to add to the agent
            auth: Authorization context for token exchange
            auth_handler_name: Name of the authorization handler.
            turn_context: Turn context for the operation
            auth_token: Optional bearer token for authentication

        Returns:
            ChatAgent instance with MCP tools registered, or None if creation failed
        """
        try:
            # Exchange token if not provided
            if not auth_token:
                scopes = get_mcp_platform_authentication_scope()
                authToken = await auth.exchange_token(turn_context, scopes, auth_handler_name)
                auth_token = authToken.token

            agentic_app_id = Utility.resolve_agent_identity(turn_context, auth_token)

            self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

            options = ToolOptions(orchestrator_name=self._orchestrator_name)

            # Get MCP server configurations
            server_configs = await self._mcp_server_configuration_service.list_tool_servers(
                agentic_app_id=agentic_app_id,
                auth_token=auth_token,
                options=options,
            )

            self._logger.info(f"Loaded {len(server_configs)} MCP server configurations")

            # Create the agent with all tools (initial + MCP tools)
            all_tools = list(initial_tools)

            # Add servers as MCPStreamableHTTPTool instances
            for config in server_configs:
                # Use mcp_server_name if available (not None or empty), otherwise fall back to mcp_server_unique_name
                server_name = config.mcp_server_name or config.mcp_server_unique_name

                try:
                    # Prepare auth headers
                    headers = {}
                    if auth_token:
                        headers[Constants.Headers.AUTHORIZATION] = (
                            f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
                        )

                    headers[Constants.Headers.USER_AGENT] = Utility.get_user_agent_header(
                        self._orchestrator_name
                    )

                    # Create and configure MCPStreamableHTTPTool
                    mcp_tools = MCPStreamableHTTPTool(
                        name=server_name,
                        url=config.url,
                        headers=headers,
                        description=f"MCP tools from {server_name}",
                    )

                    # Let Agent Framework handle the connection automatically
                    self._logger.info(f"Created MCP plugin for '{server_name}' at {config.url}")

                    all_tools.append(mcp_tools)
                    self._connected_servers.append(mcp_tools)

                    self._logger.info(f"Added MCP plugin '{server_name}' to agent tools")

                except Exception as tool_ex:
                    self._logger.warning(
                        f"Failed to create MCP plugin for {server_name}: {tool_ex}"
                    )
                    continue

            # Create the ChatAgent
            agent = ChatAgent(
                chat_client=chat_client,
                tools=all_tools,
                instructions=agent_instructions,
            )

            self._logger.info(f"Agent created with {len(all_tools)} total tools")
            return agent

        except Exception as ex:
            self._logger.error(f"Failed to add tool servers to agent: {ex}")
            raise

    def _convert_chat_messages_to_history(
        self,
        chat_messages: Sequence[ChatMessage],
    ) -> List[ChatHistoryMessage]:
        """
        Convert Agent Framework ChatMessage objects to ChatHistoryMessage format.

        This internal helper method transforms Agent Framework's native ChatMessage
        objects into the ChatHistoryMessage format expected by the MCP platform's
        real-time threat protection endpoint.

        Args:
            chat_messages: Sequence of ChatMessage objects to convert.

        Returns:
            List of ChatHistoryMessage objects ready for the MCP platform.

        Note:
            - If message_id is None, a new UUID is generated
            - Role is extracted via the .value property of the Role object
            - Timestamp is set to current UTC time (ChatMessage has no timestamp)
            - Messages with empty or whitespace-only content are filtered out and
              logged at WARNING level. This is because ChatHistoryMessage requires
              non-empty content for validation. The filtered messages will not be
              sent to the MCP platform.
        """
        history_messages: List[ChatHistoryMessage] = []
        current_time = datetime.now(timezone.utc)

        for msg in chat_messages:
            message_id = msg.message_id if msg.message_id is not None else str(uuid.uuid4())
            if msg.role is None:
                self._logger.warning(
                    "Skipping message %s with missing role during conversion", message_id
                )
                continue
            # Defensive handling: use .value if role is an enum, otherwise convert to string
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = msg.text if msg.text is not None else ""

            # Skip messages with empty content as ChatHistoryMessage validates non-empty content
            if not content.strip():
                self._logger.warning(
                    "Skipping message %s with empty content during conversion", message_id
                )
                continue

            history_message = ChatHistoryMessage(
                id=message_id,
                role=role,
                content=content,
                timestamp=current_time,
            )
            history_messages.append(history_message)

            self._logger.debug(
                "Converted message %s with role '%s' to ChatHistoryMessage", message_id, role
            )

        return history_messages

    async def send_chat_history_messages(
        self,
        chat_messages: Sequence[ChatMessage],
        turn_context: TurnContext,
        tool_options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send chat history messages to the MCP platform for real-time threat protection.

        This is the primary implementation method that handles message conversion
        and delegation to the core tooling service.

        Args:
            chat_messages: Sequence of Agent Framework ChatMessage objects to send.
                           Can be empty - the request will still be sent to register
                           the user message from turn_context.activity.text.
            turn_context: TurnContext from the Agents SDK containing conversation info.
            tool_options: Optional configuration for the request. Defaults to
                          AgentFramework-specific options if not provided.

        Returns:
            OperationResult indicating success or failure of the operation.

        Raises:
            ValueError: If chat_messages or turn_context is None.

        Note:
            Even if chat_messages is empty or all messages are filtered during
            conversion, the request will still be sent to the MCP platform. This
            ensures the user message from turn_context.activity.text is registered
            correctly for real-time threat protection.

        Example:
            >>> service = McpToolRegistrationService()
            >>> messages = [ChatMessage(role=Role.USER, text="Hello")]
            >>> result = await service.send_chat_history_messages(messages, turn_context)
            >>> if result.succeeded:
            ...     print("Chat history sent successfully")
        """
        # Input validation
        if chat_messages is None:
            raise ValueError("chat_messages cannot be None")

        if turn_context is None:
            raise ValueError("turn_context cannot be None")

        self._logger.info(f"Send chat history initiated with {len(chat_messages)} messages")

        # Use default options if not provided
        if tool_options is None:
            tool_options = ToolOptions(orchestrator_name=self._orchestrator_name)

        # Convert messages to ChatHistoryMessage format
        history_messages = self._convert_chat_messages_to_history(chat_messages)

        # Call core service even with empty history_messages to register
        # the user message from turn_context.activity.text in the MCP platform.
        if len(history_messages) == 0:
            self._logger.info(
                "Empty history messages (either no input or all filtered), "
                "still sending to register user message"
            )

        # Delegate to core service
        result = await self._mcp_server_configuration_service.send_chat_history(
            turn_context=turn_context,
            chat_history_messages=history_messages,
            options=tool_options,
        )

        if result.succeeded:
            self._logger.info(
                f"Chat history sent successfully with {len(history_messages)} messages"
            )
        else:
            self._logger.error(f"Failed to send chat history: {result}")

        return result

    async def send_chat_history_from_store(
        self,
        chat_message_store: ChatMessageStoreProtocol,
        turn_context: TurnContext,
        tool_options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send chat history from a ChatMessageStore to the MCP platform.

        This is a convenience method that extracts messages from the store
        and delegates to send_chat_history_messages().

        Args:
            chat_message_store: ChatMessageStore containing the conversation history.
            turn_context: TurnContext from the Agents SDK containing conversation info.
            tool_options: Optional configuration for the request.

        Returns:
            OperationResult indicating success or failure of the operation.

        Raises:
            ValueError: If chat_message_store or turn_context is None.

        Example:
            >>> service = McpToolRegistrationService()
            >>> result = await service.send_chat_history_from_store(
            ...     thread.chat_message_store, turn_context
            ... )
        """
        # Input validation
        if chat_message_store is None:
            raise ValueError("chat_message_store cannot be None")

        if turn_context is None:
            raise ValueError("turn_context cannot be None")

        # Extract messages from the store
        messages = await chat_message_store.list_messages()

        # Delegate to the primary implementation
        return await self.send_chat_history_messages(
            chat_messages=messages,
            turn_context=turn_context,
            tool_options=tool_options,
        )

    async def cleanup(self):
        """Clean up any resources used by the service."""
        try:
            for plugin in self._connected_servers:
                try:
                    if hasattr(plugin, "close"):
                        await plugin.close()
                except Exception as cleanup_ex:
                    self._logger.debug(f"Error during cleanup: {cleanup_ex}")
            self._connected_servers.clear()
        except Exception as ex:
            self._logger.debug(f"Error during service cleanup: {ex}")

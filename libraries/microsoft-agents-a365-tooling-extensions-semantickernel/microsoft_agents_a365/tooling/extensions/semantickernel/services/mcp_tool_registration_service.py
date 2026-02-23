# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service implementation for Semantic Kernel.

This module provides the concrete implementation of the MCP (Model Context Protocol)
tool registration service that integrates with Semantic Kernel to add MCP tool
servers to agents.
"""

# Standard library imports
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence

# Third-party imports
from semantic_kernel import kernel as sk
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

# Local imports
from microsoft_agents.hosting.core import Authorization, TurnContext
from microsoft_agents_a365.runtime import OperationError, OperationResult
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
    Provides services related to tools in the Semantic Kernel.

    This service handles registration and management of MCP (Model Context Protocol)
    tool servers with Semantic Kernel agents.
    """

    _orchestrator_name: str = "SemanticKernel"

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the MCP Tool Registration Service for Semantic Kernel.

        Args:
            logger: Logger instance for logging operations.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._mcp_server_configuration_service = McpToolServerConfigurationService(
            logger=self._logger
        )

        # Store connected plugins to keep them alive
        self._connected_plugins = []

        # Enable debug logging if configured
        if os.getenv("MCP_DEBUG_LOGGING", "false").lower() == "true":
            self._logger.setLevel(logging.DEBUG)

        # Configure strict parameter validation (prevents dynamic property creation)
        self._strict_parameter_validation = (
            os.getenv("MCP_STRICT_PARAMETER_VALIDATION", "true").lower() == "true"
        )
        if self._strict_parameter_validation:
            self._logger.info(
                "🔒 Strict parameter validation enabled - only schema-defined parameters are allowed"
            )
        else:
            self._logger.info(
                "🔓 Strict parameter validation disabled - dynamic parameters are allowed"
            )

    # ============================================================================
    # Public Methods
    # ============================================================================

    async def add_tool_servers_to_agent(
        self,
        kernel: sk.Kernel,
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
        auth_token: Optional[str] = None,
    ) -> None:
        """
        Adds the A365 MCP Tool Servers to the specified kernel.

        Args:
            kernel: The Semantic Kernel instance to which the tools will be added.
            auth: Authorization handler for token exchange.
            auth_handler_name: Name of the authorization handler.
            context: Turn context for the current operation.
            auth_token: Authentication token to access the MCP servers.

        Raises:
            ValueError: If kernel is None or required parameters are invalid.
            Exception: If there's an error connecting to or configuring MCP servers.
        """

        if not auth_token:
            scopes = get_mcp_platform_authentication_scope()
            authToken = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = authToken.token

        agentic_app_id = Utility.resolve_agent_identity(context, auth_token)
        self._validate_inputs(kernel, agentic_app_id, auth_token)

        # Get and process servers
        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        servers = await self._mcp_server_configuration_service.list_tool_servers(
            agentic_app_id, auth_token, options
        )
        self._logger.info(f"🔧 Adding MCP tools from {len(servers)} servers")

        # Process each server (matching C# foreach pattern)
        for server in servers:
            try:
                headers = {
                    Constants.Headers.AUTHORIZATION: (
                        f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
                    ),
                }

                headers[Constants.Headers.USER_AGENT] = Utility.get_user_agent_header(
                    self._orchestrator_name
                )

                # Use the URL from server (always populated by the configuration service)
                server_url = server.url

                # Use mcp_server_name if available (not None or empty),
                # otherwise fall back to mcp_server_unique_name
                server_name = server.mcp_server_name or server.mcp_server_unique_name

                plugin = MCPStreamableHttpPlugin(
                    name=server_name,
                    url=server_url,
                    headers=headers,
                )

                # Connect the plugin
                await plugin.connect()

                # Add plugin to kernel
                kernel.add_plugin(plugin, server_name)

                # Store reference to keep plugin alive throughout application lifecycle.
                # By storing plugin references in _connected_plugins, we prevent
                # Python's garbage collector from cleaning up the plugin objects.
                # The connections remain active throughout the application lifecycle.
                # Tools can be invoked because their underlying connections stay alive.
                self._connected_plugins.append(plugin)

                self._logger.info(
                    f"✅ Connected and added MCP plugin for: {server.mcp_server_name}"
                )

            except Exception as e:
                self._logger.error(f"Failed to add tools from {server.mcp_server_name}: {str(e)}")

        self._logger.info("✅ Successfully configured MCP tool servers for the agent!")

    # ============================================================================
    # Private Methods - Input Validation & Processing
    # ============================================================================

    def _validate_inputs(self, kernel: Any, agentic_app_id: str, auth_token: str) -> None:
        """Validate all required inputs."""
        if kernel is None:
            raise ValueError("kernel cannot be None")
        if not agentic_app_id or not agentic_app_id.strip():
            raise ValueError("agentic_app_id cannot be null or empty")
        if not auth_token or not auth_token.strip():
            raise ValueError("auth_token cannot be null or empty")

    # ============================================================================
    # Private Methods - Kernel Function Creation
    # ============================================================================

    def _get_plugin_name_from_server_name(self, server_name: str) -> str:
        """Generate a clean plugin name from server name."""
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", server_name)
        return f"{clean_name}Tools"

    # ============================================================================
    # SEND CHAT HISTORY - Semantic Kernel-specific implementations
    # ============================================================================

    async def send_chat_history(
        self,
        turn_context: TurnContext,
        chat_history: ChatHistory,
        limit: Optional[int] = None,
        options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send Semantic Kernel chat history to the MCP platform.

        This method extracts messages from a Semantic Kernel ChatHistory object,
        converts them to ChatHistoryMessage format, and sends them to the MCP
        platform for real-time threat protection.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation info.
            chat_history: Semantic Kernel ChatHistory object containing messages.
            limit: Optional maximum number of messages to send. If specified,
                   sends the most recent N messages. If None, sends all messages.
            options: Optional configuration for the request.

        Returns:
            OperationResult indicating success or failure.

        Raises:
            ValueError: If turn_context or chat_history is None.

        Example:
            >>> from semantic_kernel.contents import ChatHistory
            >>> from microsoft_agents_a365.tooling.extensions.semantickernel import (
            ...     McpToolRegistrationService
            ... )
            >>>
            >>> service = McpToolRegistrationService()
            >>> chat_history = ChatHistory()
            >>> chat_history.add_user_message("Hello!")
            >>> chat_history.add_assistant_message("Hi there!")
            >>>
            >>> result = await service.send_chat_history(
            ...     turn_context, chat_history, limit=50
            ... )
            >>> if result.succeeded:
            ...     print("Chat history sent successfully")
        """
        # Validate inputs
        if turn_context is None:
            raise ValueError("turn_context cannot be None")
        if chat_history is None:
            raise ValueError("chat_history cannot be None")

        try:
            # Extract messages from ChatHistory
            messages = list(chat_history.messages)
            self._logger.debug(f"Extracted {len(messages)} messages from ChatHistory")

            # Apply limit if specified
            if limit is not None and limit > 0 and len(messages) > limit:
                self._logger.info(f"Applying limit of {limit} to {len(messages)} messages")
                messages = messages[-limit:]  # Take the most recent N messages

            # Delegate to the list-based method
            return await self.send_chat_history_messages(
                turn_context=turn_context,
                messages=messages,
                options=options,
            )
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as ex:
            self._logger.error(f"Failed to send chat history: {ex}")
            return OperationResult.failed(OperationError(ex))

    async def send_chat_history_messages(
        self,
        turn_context: TurnContext,
        messages: Sequence[ChatMessageContent],
        options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send Semantic Kernel chat history messages to the MCP platform.

        This method accepts a sequence of Semantic Kernel ChatMessageContent objects,
        converts them to ChatHistoryMessage format, and sends them to the MCP
        platform for real-time threat protection.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation info.
            messages: Sequence of Semantic Kernel ChatMessageContent objects to send.
            options: Optional configuration for the request.

        Returns:
            OperationResult indicating success or failure.

        Raises:
            ValueError: If turn_context or messages is None.

        Example:
            >>> from semantic_kernel.contents import ChatMessageContent, AuthorRole
            >>> from microsoft_agents_a365.tooling.extensions.semantickernel import (
            ...     McpToolRegistrationService
            ... )
            >>>
            >>> service = McpToolRegistrationService()
            >>> messages = [
            ...     ChatMessageContent(role=AuthorRole.USER, content="Hello!"),
            ...     ChatMessageContent(role=AuthorRole.ASSISTANT, content="Hi there!"),
            ... ]
            >>>
            >>> result = await service.send_chat_history_messages(
            ...     turn_context, messages
            ... )
            >>> if result.succeeded:
            ...     print("Chat history sent successfully")
        """
        # Validate inputs
        if turn_context is None:
            raise ValueError("turn_context cannot be None")
        if messages is None:
            raise ValueError("messages cannot be None")

        self._logger.info(f"Sending {len(messages)} Semantic Kernel messages as chat history")

        # Set default options
        if options is None:
            options = ToolOptions(orchestrator_name=self._orchestrator_name)
        elif options.orchestrator_name is None:
            options.orchestrator_name = self._orchestrator_name

        try:
            # Convert Semantic Kernel messages to ChatHistoryMessage format
            chat_history_messages = self._convert_sk_messages_to_chat_history(messages)

            # Call core service even with empty chat_history_messages
            if len(chat_history_messages) == 0:
                self._logger.info(
                    "Empty chat history messages (either no input or all filtered), "
                    "still sending to register user message"
                )

            self._logger.debug(
                f"Converted {len(chat_history_messages)} messages to ChatHistoryMessage format"
            )

            # Delegate to core service
            return await self._mcp_server_configuration_service.send_chat_history(
                turn_context=turn_context,
                chat_history_messages=chat_history_messages,
                options=options,
            )
        except ValueError:
            # Re-raise validation errors from the core service
            raise
        except Exception as ex:
            self._logger.error(f"Failed to send chat history messages: {ex}")
            return OperationResult.failed(OperationError(ex))

    # ============================================================================
    # PRIVATE HELPER METHODS - Message Conversion
    # ============================================================================

    def _convert_sk_messages_to_chat_history(
        self,
        messages: Sequence[ChatMessageContent],
    ) -> List[ChatHistoryMessage]:
        """
        Convert Semantic Kernel ChatMessageContent objects to ChatHistoryMessage format.

        Args:
            messages: Sequence of Semantic Kernel ChatMessageContent objects.

        Returns:
            List of ChatHistoryMessage objects. Messages that cannot be converted
            are filtered out with a warning log.
        """
        chat_history_messages: List[ChatHistoryMessage] = []

        for idx, message in enumerate(messages):
            converted = self._convert_single_sk_message(message, idx)
            if converted is not None:
                chat_history_messages.append(converted)

        self._logger.info(
            f"Converted {len(chat_history_messages)} of {len(messages)} messages "
            "to ChatHistoryMessage format"
        )
        return chat_history_messages

    def _convert_single_sk_message(
        self,
        message: ChatMessageContent,
        index: int = 0,
    ) -> Optional[ChatHistoryMessage]:
        """
        Convert a single Semantic Kernel message to ChatHistoryMessage format.

        Args:
            message: Single Semantic Kernel ChatMessageContent message.
            index: Index of the message in the list (for logging).

        Returns:
            ChatHistoryMessage object or None if conversion fails.
        """
        try:
            # Skip None messages
            if message is None:
                self._logger.warning(f"Skipping null message at index {index}")
                return None

            # Map role to string
            role = self._map_author_role(message.role)

            # Extract content
            content = self._extract_content(message)
            if not content or not content.strip():
                self._logger.warning(f"Skipping message at index {index} with empty content")
                return None

            # Extract or generate ID
            msg_id = self._extract_or_generate_id(message, index)

            # Extract or generate timestamp
            timestamp = self._extract_or_generate_timestamp(message, index)

            self._logger.debug(
                f"Converting message {index}: role={role}, "
                f"id={msg_id}, has_timestamp={timestamp is not None}"
            )

            return ChatHistoryMessage(
                id=msg_id,
                role=role,
                content=content,
                timestamp=timestamp,
            )
        except Exception as ex:
            self._logger.error(f"Failed to convert message at index {index}: {ex}")
            return None

    def _map_author_role(self, role: AuthorRole) -> str:
        """
        Map Semantic Kernel AuthorRole enum to lowercase string.

        Args:
            role: AuthorRole enum value.

        Returns:
            Lowercase string representation of the role.
        """
        return role.name.lower()

    def _extract_content(self, message: ChatMessageContent) -> str:
        """
        Extract text content from a ChatMessageContent.

        Args:
            message: Semantic Kernel ChatMessageContent object.

        Returns:
            Content string (may be empty). Returns empty string for unexpected
            types to avoid unintentionally exposing sensitive data.
        """
        content = message.content

        if content is None:
            return ""

        # If content is already a string, return it directly
        if isinstance(content, str):
            return content

        # For unexpected types, log a warning and return empty string to avoid
        # unintentionally stringifying objects that might contain sensitive data
        content_type = type(content).__name__
        self._logger.warning(
            f"Unexpected content type '{content_type}' encountered. "
            "Returning empty string to avoid potential data exposure."
        )
        return ""

    def _extract_or_generate_id(
        self,
        message: ChatMessageContent,
        index: int,
    ) -> str:
        """
        Extract message ID from metadata or generate a new UUID.

        Args:
            message: Semantic Kernel ChatMessageContent object.
            index: Message index for logging.

        Returns:
            Message ID string.
        """
        # Try to get existing ID from metadata
        if message.metadata and "id" in message.metadata:
            existing_id = message.metadata["id"]
            if existing_id:
                return str(existing_id)

        # Generate new UUID
        generated_id = str(uuid.uuid4())
        self._logger.debug(f"Generated UUID {generated_id} for message at index {index}")
        return generated_id

    def _extract_or_generate_timestamp(
        self,
        message: ChatMessageContent,
        index: int,
    ) -> datetime:
        """
        Extract timestamp from metadata or generate current UTC time.

        Args:
            message: Semantic Kernel ChatMessageContent object.
            index: Message index for logging.

        Returns:
            Timestamp as datetime object.
        """
        # Try to get existing timestamp from metadata
        if message.metadata:
            existing_timestamp = message.metadata.get("timestamp") or message.metadata.get(
                "created_at"
            )
            if existing_timestamp:
                if isinstance(existing_timestamp, datetime):
                    return existing_timestamp
                elif isinstance(existing_timestamp, (int, float)):
                    # Unix timestamp
                    return datetime.fromtimestamp(existing_timestamp, tz=timezone.utc)
                elif isinstance(existing_timestamp, str):
                    try:
                        return datetime.fromisoformat(existing_timestamp.replace("Z", "+00:00"))
                    except (ValueError, TypeError) as ex:
                        self._logger.debug(
                            f"Failed to parse timestamp '{existing_timestamp}' at index {index}: {ex}"
                        )

        # Use current UTC time
        self._logger.debug(f"Using current UTC time for message at index {index}")
        return datetime.now(timezone.utc)

    # ============================================================================
    # Cleanup Methods
    # ============================================================================

    async def cleanup_connections(self) -> None:
        """Clean up all connected MCP plugins."""
        self._logger.info(f"🧹 Cleaning up {len(self._connected_plugins)} MCP plugin connections")

        for plugin in self._connected_plugins:
            try:
                if hasattr(plugin, "close"):
                    await plugin.close()
                elif hasattr(plugin, "disconnect"):
                    await plugin.disconnect()
                self._logger.debug(
                    f"✅ Closed connection for plugin: {getattr(plugin, 'name', 'unknown')}"
                )
            except Exception as e:
                self._logger.warning(f"⚠️ Error closing plugin connection: {e}")

        self._connected_plugins.clear()
        self._logger.info("✅ All MCP plugin connections cleaned up")

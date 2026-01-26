# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service for OpenAI.

This module provides OpenAI-specific extensions for MCP tool registration,
including methods to send chat history from OpenAI Sessions and message lists.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from agents import Agent
from agents.items import TResponseInputItem
from agents.mcp import (
    MCPServerStreamableHttp,
    MCPServerStreamableHttpParams,
)
from agents.memory import Session
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
    ) -> Agent:
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

        if auth_token is None or auth_token.strip() == "":
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
            # Use mcp_server_name if available (not None or empty), otherwise fall back to mcp_server_unique_name
            server_name = server_config.mcp_server_name or server_config.mcp_server_unique_name
            # Use the URL from config (always populated by the configuration service)
            server_url = server_config.url
            server_info = MCPServerInfo(
                name=server_name,
                url=server_url,
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
                raise

        self._logger.info("No new MCP servers to add to agent")
        return agent

    async def _cleanup_servers(self, servers: List[MCPServerStreamableHttp]) -> None:
        """Clean up connected MCP servers"""
        for server in servers:
            try:
                if hasattr(server, "cleanup"):
                    await server.cleanup()
            except Exception as e:
                # Log cleanup errors but don't raise them
                self._logger.debug(f"Error during server cleanup: {e}")

    async def cleanup_all_servers(self) -> None:
        """Clean up all connected MCP servers"""
        if hasattr(self, "_connected_servers"):
            await self._cleanup_servers(self._connected_servers)
            self._connected_servers = []

    # --------------------------------------------------------------------------
    # SEND CHAT HISTORY - OpenAI-specific implementations
    # --------------------------------------------------------------------------

    async def send_chat_history(
        self,
        turn_context: TurnContext,
        session: Session,
        limit: Optional[int] = None,
        options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Extract chat history from an OpenAI Session and send it to the MCP platform.

        This method extracts messages from an OpenAI Session object using get_items()
        and sends them to the MCP platform for real-time threat protection.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation info.
                          Must have a valid activity with conversation.id, activity.id,
                          and activity.text.
            session: OpenAI Session instance to extract messages from. Must support
                     the get_items() method which returns a list of TResponseInputItem.
            limit: Optional maximum number of items to retrieve from session.
                   If None, retrieves all items.
            options: Optional ToolOptions for customization. If not provided,
                     uses default options with orchestrator_name="OpenAI".

        Returns:
            OperationResult indicating success or failure. On success, returns
            OperationResult.success(). On failure, returns OperationResult.failed()
            with error details.

        Raises:
            ValueError: If turn_context is None or session is None.

        Example:
            >>> from agents import Agent, Runner
            >>> from microsoft_agents_a365.tooling.extensions.openai import (
            ...     McpToolRegistrationService
            ... )
            >>>
            >>> service = McpToolRegistrationService()
            >>> agent = Agent(name="my-agent", model="gpt-4")
            >>>
            >>> # In your agent handler:
            >>> async with Runner.run(agent, messages) as result:
            ...     session = result.session
            ...     op_result = await service.send_chat_history(
            ...         turn_context, session
            ...     )
            ...     if op_result.succeeded:
            ...         print("Chat history sent successfully")
        """
        # Validate inputs
        if turn_context is None:
            raise ValueError("turn_context cannot be None")
        if session is None:
            raise ValueError("session cannot be None")

        try:
            # Extract messages from session
            self._logger.info("Extracting messages from OpenAI session")
            if limit is not None:
                messages = session.get_items(limit=limit)
            else:
                messages = session.get_items()

            self._logger.debug(f"Retrieved {len(messages)} items from session")

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
            self._logger.error(f"Failed to send chat history from session: {ex}")
            return OperationResult.failed(OperationError(ex))

    async def send_chat_history_messages(
        self,
        turn_context: TurnContext,
        messages: List[TResponseInputItem],
        options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Send OpenAI chat history messages to the MCP platform for threat protection.

        This method accepts a list of OpenAI TResponseInputItem messages, converts
        them to ChatHistoryMessage format, and sends them to the MCP platform.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation info.
                          Must have a valid activity with conversation.id, activity.id,
                          and activity.text.
            messages: List of OpenAI TResponseInputItem messages to send. Supports
                      UserMessage, AssistantMessage, SystemMessage, and other OpenAI
                      message types.
            options: Optional ToolOptions for customization. If not provided,
                     uses default options with orchestrator_name="OpenAI".

        Returns:
            OperationResult indicating success or failure. On success, returns
            OperationResult.success(). On failure, returns OperationResult.failed()
            with error details.

        Raises:
            ValueError: If turn_context is None or messages is None.

        Example:
            >>> from microsoft_agents_a365.tooling.extensions.openai import (
            ...     McpToolRegistrationService
            ... )
            >>>
            >>> service = McpToolRegistrationService()
            >>> messages = [
            ...     {"role": "user", "content": "Hello"},
            ...     {"role": "assistant", "content": "Hi there!"},
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

        # Handle empty list as no-op
        if len(messages) == 0:
            self._logger.info("Empty message list provided, returning success")
            return OperationResult.success()

        self._logger.info(f"Sending {len(messages)} OpenAI messages as chat history")

        # Set default options
        if options is None:
            options = ToolOptions(orchestrator_name=self._orchestrator_name)
        elif options.orchestrator_name is None:
            options.orchestrator_name = self._orchestrator_name

        try:
            # Convert OpenAI messages to ChatHistoryMessage format
            chat_history_messages = self._convert_openai_messages_to_chat_history(messages)

            if len(chat_history_messages) == 0:
                self._logger.warning("No messages could be converted to chat history format")
                return OperationResult.success()

            self._logger.debug(
                f"Converted {len(chat_history_messages)} messages to ChatHistoryMessage format"
            )

            # Delegate to core service
            return await self.config_service.send_chat_history(
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

    # --------------------------------------------------------------------------
    # PRIVATE HELPER METHODS - Message Conversion
    # --------------------------------------------------------------------------

    def _convert_openai_messages_to_chat_history(
        self, messages: List[TResponseInputItem]
    ) -> List[ChatHistoryMessage]:
        """
        Convert a list of OpenAI messages to ChatHistoryMessage format.

        Args:
            messages: List of OpenAI TResponseInputItem messages.

        Returns:
            List of ChatHistoryMessage objects. Messages that cannot be converted
            are filtered out with a warning log.
        """
        chat_history_messages: List[ChatHistoryMessage] = []

        for idx, message in enumerate(messages):
            converted = self._convert_single_message(message, idx)
            if converted is not None:
                chat_history_messages.append(converted)

        self._logger.info(
            f"Converted {len(chat_history_messages)} of {len(messages)} messages "
            "to ChatHistoryMessage format"
        )
        return chat_history_messages

    def _convert_single_message(
        self, message: TResponseInputItem, index: int = 0
    ) -> Optional[ChatHistoryMessage]:
        """
        Convert a single OpenAI message to ChatHistoryMessage format.

        Args:
            message: Single OpenAI TResponseInputItem message.
            index: Index of the message in the list (for logging).

        Returns:
            ChatHistoryMessage object or None if conversion fails.
        """
        try:
            role = self._extract_role(message)
            content = self._extract_content(message)
            msg_id = self._extract_id(message)
            timestamp = self._extract_timestamp(message)

            self._logger.debug(
                f"Converting message {index}: role={role}, "
                f"has_id={msg_id is not None}, has_timestamp={timestamp is not None}"
            )

            # Skip messages with empty content after extraction
            # The ChatHistoryMessage validator requires non-empty content
            if not content or not content.strip():
                self._logger.warning(f"Message {index} has empty content, skipping")
                return None

            return ChatHistoryMessage(
                id=msg_id,
                role=role,
                content=content,
                timestamp=timestamp,
            )
        except Exception as ex:
            self._logger.error(f"Failed to convert message {index}: {ex}")
            return None

    def _extract_role(self, message: TResponseInputItem) -> str:
        """
        Extract the role from an OpenAI message.

        Role mapping:
        - UserMessage or role="user" -> "user"
        - AssistantMessage or role="assistant" -> "assistant"
        - SystemMessage or role="system" -> "system"
        - ResponseOutputMessage with role="assistant" -> "assistant"
        - Unknown types -> "user" (default fallback with warning)

        Args:
            message: OpenAI message object.

        Returns:
            Role string: "user", "assistant", or "system".
        """
        # Check for role attribute directly
        if hasattr(message, "role"):
            role = message.role
            if role in ("user", "assistant", "system"):
                return role

        # Check message type by class name
        type_name = type(message).__name__

        if "UserMessage" in type_name or "user" in type_name.lower():
            return "user"
        elif "AssistantMessage" in type_name or "assistant" in type_name.lower():
            return "assistant"
        elif "SystemMessage" in type_name or "system" in type_name.lower():
            return "system"
        elif "ResponseOutputMessage" in type_name:
            # ResponseOutputMessage typically has role attribute
            if hasattr(message, "role") and message.role == "assistant":
                return "assistant"
            return "assistant"  # Default for response output

        # For dict-like objects
        if isinstance(message, dict):
            role = message.get("role", "")
            if role in ("user", "assistant", "system"):
                return role

        # Default fallback with warning
        self._logger.warning(f"Unknown message type {type_name}, defaulting to 'user' role")
        return "user"

    def _extract_content(self, message: TResponseInputItem) -> str:
        """
        Extract text content from an OpenAI message.

        Content extraction priority:
        1. If message has .content as string -> use directly
        2. If message has .content as list -> concatenate all text parts
        3. If message has .text attribute -> use directly
        4. If content is empty/None -> return empty string with warning

        Args:
            message: OpenAI message object.

        Returns:
            Extracted text content as string.
        """
        content = ""

        # Try .content attribute first
        if hasattr(message, "content"):
            raw_content = message.content

            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                # Concatenate text parts from content list
                text_parts = []
                for part in raw_content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif hasattr(part, "text"):
                        text_parts.append(str(part.text))
                    elif isinstance(part, dict):
                        if "text" in part:
                            text_parts.append(str(part["text"]))
                        elif part.get("type") == "text" and "text" in part:
                            text_parts.append(str(part["text"]))
                content = " ".join(text_parts)

        # Try .text attribute as fallback
        if not content and hasattr(message, "text"):
            content = str(message.text) if message.text else ""

        # Try dict-like access
        if not content and isinstance(message, dict):
            content = message.get("content", "") or message.get("text", "") or ""
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(str(part["text"]))
                content = " ".join(text_parts)

        if not content:
            self._logger.warning("Message has empty content, using empty string")

        return content

    def _extract_id(self, message: TResponseInputItem) -> str:
        """
        Extract or generate a unique ID for the message.

        If the message has an existing ID, it is preserved. Otherwise,
        a new UUID is generated.

        Args:
            message: OpenAI message object.

        Returns:
            Message ID as string.
        """
        # Try to get existing ID
        existing_id = None

        if hasattr(message, "id") and message.id:
            existing_id = str(message.id)
        elif isinstance(message, dict) and message.get("id"):
            existing_id = str(message["id"])

        if existing_id:
            return existing_id

        # Generate new UUID
        generated_id = str(uuid.uuid4())
        self._logger.debug(f"Generated UUID {generated_id} for message without ID")
        return generated_id

    def _extract_timestamp(self, message: TResponseInputItem) -> datetime:
        """
        Extract or generate a timestamp for the message.

        If the message has an existing timestamp, it is preserved. Otherwise,
        the current UTC time is used.

        Args:
            message: OpenAI message object.

        Returns:
            Timestamp as datetime object.
        """
        # Try to get existing timestamp
        existing_timestamp = None

        if hasattr(message, "timestamp") and message.timestamp:
            existing_timestamp = message.timestamp
        elif hasattr(message, "created_at") and message.created_at:
            existing_timestamp = message.created_at
        elif isinstance(message, dict):
            existing_timestamp = message.get("timestamp") or message.get("created_at")

        if existing_timestamp:
            # Convert to datetime if needed
            if isinstance(existing_timestamp, datetime):
                return existing_timestamp
            elif isinstance(existing_timestamp, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(existing_timestamp, tz=timezone.utc)
            elif isinstance(existing_timestamp, str):
                # Try ISO format parsing
                try:
                    return datetime.fromisoformat(existing_timestamp.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Use current UTC time
        self._logger.debug("Using current UTC time for message without timestamp")
        return datetime.now(timezone.utc)

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service implementation for Semantic Kernel.

This module provides the concrete implementation of the MCP (Model Context Protocol)
tool registration service that integrates with Semantic Kernel to add MCP tool
servers to agents.
"""

# Standard library imports
import asyncio
import contextlib
import functools
import logging
import os
import re
import uuid
import weakref
from datetime import datetime, timezone
from typing import List, Optional, Sequence

# Third-party imports
from semantic_kernel import kernel as sk
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent
from semantic_kernel.functions import KernelPlugin

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
    is_development_environment,
)

logger = logging.getLogger(__name__)

# Kernel plugins created by add_tool_servers_to_agent, keyed by id(). Module-level so plugins
# added by any service instance are recognized; entries are dropped when the plugin is
# garbage collected. KernelPlugin is unhashable, hence id() keys plus an identity check.
_sdk_managed_plugins: "weakref.WeakValueDictionary[int, KernelPlugin]" = (
    weakref.WeakValueDictionary()
)

# MCP plugins created by add_tool_servers_to_agent, each mapped to a weak reference to the kernel
# plugin it was added as (None if that can't be tracked). Kernel.clone() copies KernelPlugin
# wrappers but shares their functions, so cloned plugins are recognized by the MCP plugin that
# owns them.
_AddedAs = Optional["weakref.ref[KernelPlugin]"]
_sdk_managed_mcp_plugins: "weakref.WeakKeyDictionary[MCPStreamableHttpPlugin, _AddedAs]" = (
    weakref.WeakKeyDictionary()
)

# Background tasks that close MCP plugins; kept so they are not garbage collected before they
# finish.
_closing_tasks: "set[asyncio.Task[None]]" = set()

# How long cleanup_connections() waits for plugins that later calls replaced to finish closing.
_CLOSE_TIMEOUT_SECONDS = 30


def _is_sdk_mcp_plugin(owner: object) -> bool:
    """Return True if the object is an MCP plugin created by this service."""
    try:
        return owner in _sdk_managed_mcp_plugins
    except TypeError:
        # Not hashable or weak-referenceable, so it was not created by this service.
        return False


def _function_owner(function: object) -> object:
    """Return the object whose method a kernel function calls, if any."""
    method = getattr(function, "method", None)
    # MCP tools are partial(mcp_plugin.call_tool, tool_name)
    if isinstance(method, functools.partial):
        method = method.func
    return getattr(method, "__self__", None)


def _sdk_mcp_plugins_of(plugin: KernelPlugin) -> List[MCPStreamableHttpPlugin]:
    """Return the MCP plugins created by this service whose functions the kernel plugin calls."""
    functions = getattr(plugin, "functions", None)
    if not isinstance(functions, dict):
        return []
    owners = (_function_owner(function) for function in functions.values())
    return [owner for owner in owners if owner is not None and _is_sdk_mcp_plugin(owner)]


def _is_sdk_managed_plugin(plugin: KernelPlugin) -> bool:
    """Return True if the kernel plugin was added by this service, or cloned from one that was."""
    return _sdk_managed_plugins.get(id(plugin)) is plugin or bool(_sdk_mcp_plugins_of(plugin))


def _mcp_plugins_behind(plugins: Sequence[KernelPlugin]) -> List[MCPStreamableHttpPlugin]:
    """Return each MCP plugin created by this service that backs one of the kernel plugins."""
    owners: "dict[int, MCPStreamableHttpPlugin]" = {}
    for plugin in plugins:
        found = _sdk_mcp_plugins_of(plugin)
        if not found:
            # A server without tools or prompts gives its kernel plugin no functions.
            found = [
                owner
                for owner, added_as in list(_sdk_managed_mcp_plugins.items())
                if added_as is not None and added_as() is plugin
            ]
        for owner in found:
            owners.setdefault(id(owner), owner)
    return list(owners.values())


def _register_sdk_managed_plugin(
    kernel_plugin: Optional[KernelPlugin], mcp_plugin: MCPStreamableHttpPlugin
) -> None:
    """Record a kernel plugin added by this service and the MCP plugin behind it."""
    try:
        added_as: _AddedAs = weakref.ref(kernel_plugin)
    except TypeError:
        added_as = None
    try:
        _sdk_managed_mcp_plugins[mcp_plugin] = added_as
    except TypeError:
        pass
    try:
        _sdk_managed_plugins[id(kernel_plugin)] = kernel_plugin
    except TypeError:
        # Not weak-referenceable (e.g. None from a custom kernel), so it cannot be tracked.
        pass


async def _close_plugin(plugin: MCPStreamableHttpPlugin) -> None:
    """Close an MCP plugin, logging instead of raising if that fails."""
    try:
        await plugin.close()
    except Exception as error:
        logger.debug(f"Error closing MCP plugin '{getattr(plugin, 'name', 'unknown')}': {error}")


def _start_closing(plugin: MCPStreamableHttpPlugin) -> "asyncio.Task[None]":
    """Close an MCP plugin in a task of its own, so a slow or failing close holds up no caller.

    ``MCPPluginBase.close()`` only signals the plugin's own connection task and waits for it, so
    any task can close a connected plugin.
    """
    closing_task = asyncio.ensure_future(_close_plugin(plugin))
    _closing_tasks.add(closing_task)
    closing_task.add_done_callback(_closing_tasks.discard)
    return closing_task


_warned_connection_task_missing = False


def _warn_connection_task_missing(plugin: MCPStreamableHttpPlugin) -> None:
    """Warn once that an MCP plugin doesn't expose the background task that connects it."""
    global _warned_connection_task_missing
    if _warned_connection_task_missing:
        return
    _warned_connection_task_missing = True
    logger.warning(
        f"MCP plugin '{getattr(plugin, 'name', 'unknown')}' ({type(plugin).__name__}) has no "
        "_current_task connection task, which this Semantic Kernel version was expected to set. "
        "A server that fails to connect can keep add_tool_servers_to_agent from returning."
    )


async def _close_after_cancelled_connect(
    plugin: MCPStreamableHttpPlugin, connect_task: "asyncio.Future[None]"
) -> None:
    """Close a plugin whose connection kept running after its connect() was cancelled."""
    # Let connect() start its background connection task if it has not yet.
    await asyncio.sleep(0)
    connection_task = getattr(plugin, "_current_task", None)
    waiting = {connect_task}
    if isinstance(connection_task, asyncio.Future):
        waiting.add(connection_task)
    await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
    if connect_task.done() and not connect_task.cancelled() and connect_task.exception() is None:
        # Connected: close() stops the background task, which then closes the connection itself.
        with contextlib.suppress(Exception):
            await plugin.close()
    else:
        # The connection failed; its background task already closed what it had opened.
        connect_task.cancel()
        if isinstance(connection_task, asyncio.Future) and connection_task.done():
            if not connection_task.cancelled():
                connection_task.exception()


async def _connect_plugin(plugin: MCPStreamableHttpPlugin) -> None:
    """Connect an MCP plugin, raising instead of waiting forever when the connection fails.

    ``MCPPluginBase.connect()`` opens the connection in a background task and waits for that
    task to report that it is ready. When the server rejects the session (for example with
    HTTP 403), the background task can end without reporting, and ``connect()`` never returns.
    When the transport cannot be created, the task reports ready and then fails, and
    ``connect()`` returns without a connection. Both raise ``ConnectionError`` here.
    If this call is cancelled, the background task keeps connecting, so the plugin is closed
    once it is done. The background task is ``MCPPluginBase._current_task``; if a Semantic
    Kernel version doesn't set it, a warning is logged and only ``connect()`` is awaited.
    """
    connect_task = asyncio.ensure_future(plugin.connect())
    try:
        # connect() starts its background task before it first waits.
        await asyncio.sleep(0)
        connection_task = getattr(plugin, "_current_task", None)
        pending = {connect_task}
        if isinstance(connection_task, asyncio.Future):
            pending.add(connection_task)
        elif not connect_task.done():
            _warn_connection_task_missing(plugin)
        await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
    except BaseException:
        closing_task = asyncio.ensure_future(_close_after_cancelled_connect(plugin, connect_task))
        _closing_tasks.add(closing_task)
        closing_task.add_done_callback(_closing_tasks.discard)
        raise
    if connect_task.done():
        connect_task.result()
        if not isinstance(connection_task, asyncio.Future) or not connection_task.done():
            return
        # connect() returned, but the background task had already ended: nothing is connected.
    else:
        # The background task ended without reporting that it is ready.
        connect_task.cancel()
        await asyncio.wait({connect_task})
    error = None if connection_task.cancelled() else connection_task.exception()
    raise ConnectionError(f"Failed to connect to MCP server '{plugin.name}'") from error


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
        # Background closes of plugins that a later call replaced; cleanup_connections() waits
        # for them.
        self._pending_closes: "set[asyncio.Task[None]]" = set()

        # Enable debug logging if configured
        if os.getenv("MCP_DEBUG_LOGGING", "false").lower() == "true":
            self._logger.setLevel(logging.DEBUG)

        # Configure strict parameter validation (prevents dynamic property creation)
        self._strict_parameter_validation = (
            os.getenv("MCP_STRICT_PARAMETER_VALIDATION", "true").lower() == "true"
        )
        if self._strict_parameter_validation:
            self._logger.info(
                "Strict parameter validation enabled - only schema-defined parameters are allowed"
            )
        else:
            self._logger.info(
                "Strict parameter validation disabled - dynamic parameters are allowed"
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

        Each MCP plugin carries the current caller's Authorization token in its request
        headers. Plugins added by an earlier call, including copies made by ``Kernel.clone()``,
        are removed from the kernel before anything else happens, and fresh plugins are added
        for this turn. A kernel that is reused from one turn to the next therefore does not
        keep an earlier user's or agent identity's plugin, even when a server is not
        rediscovered or fails to connect. The MCP connections behind the removed plugins are
        closed in the background, which also ends them for any ``Kernel.clone()`` copy that
        still shares those plugins, and ``cleanup_connections()`` waits for those closes to
        finish. A server that fails to connect, for example because it rejects the caller, is
        skipped. Because the kernel is modified in place, turns that run concurrently must each
        use their own kernel, for example a ``clone()`` of a base kernel without these plugins.

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
        # Remove plugins added by an earlier call before anything here can fail. They carry the
        # token of whichever user or agent identity that call ran for.
        if kernel is not None:
            stale_plugins = {
                name: plugin
                for name, plugin in kernel.plugins.items()
                if _is_sdk_managed_plugin(plugin)
            }
            for name in stale_plugins:
                del kernel.plugins[name]
            if stale_plugins:
                self._logger.info(
                    f"Removed {len(stale_plugins)} MCP plugins added by an earlier call"
                )
                self._close_replaced_plugins(_mcp_plugins_behind(list(stale_plugins.values())))

        is_dev = is_development_environment()
        if not auth_token and not is_dev:
            # Only exchange a token in production; dev mode uses BEARER_TOKEN* env vars instead.
            scopes = get_mcp_platform_authentication_scope()
            authToken = await auth.exchange_token(context, scopes, auth_handler_name)
            auth_token = authToken.token

        # In dev mode, agentic_app_id is not needed for manifest-based discovery.
        agentic_app_id = "" if is_dev else Utility.resolve_agent_identity(context, auth_token)
        self._validate_inputs(kernel, agentic_app_id, auth_token)

        # Get and process servers
        options = ToolOptions(orchestrator_name=self._orchestrator_name)
        servers = await self._mcp_server_configuration_service.list_tool_servers(
            agentic_app_id,
            auth_token,
            options,
            authorization=auth,
            auth_handler_name=auth_handler_name,
            turn_context=context,
        )
        self._logger.info(f"Adding MCP tools from {len(servers)} servers")

        # Process each server (matching C# foreach pattern)
        for server in servers:
            try:
                base_headers = {
                    Constants.Headers.USER_AGENT: Utility.get_user_agent_header(
                        self._orchestrator_name
                    )
                }
                server_headers = dict(server.headers) if server.headers else {}
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
                await _connect_plugin(plugin)

                try:
                    # Add plugin to kernel
                    kernel_plugin = kernel.add_plugin(plugin, server_name)
                except Exception:
                    # For example a server name that isn't a valid plugin name. The plugin is
                    # connected but can't be used, so close it instead of leaving it open.
                    self._close_in_background(plugin)
                    raise
                _register_sdk_managed_plugin(kernel_plugin, plugin)

                # Store reference to keep plugin alive throughout application lifecycle.
                # By storing plugin references in _connected_plugins, we prevent
                # Python's garbage collector from cleaning up the plugin objects.
                # The connections remain active throughout the application lifecycle.
                # Tools can be invoked because their underlying connections stay alive.
                self._connected_plugins.append(plugin)

                self._logger.info(f"Connected and added MCP plugin for: {server.mcp_server_name}")

            except Exception as e:
                self._logger.error(f"Failed to add tools from {server.mcp_server_name}: {str(e)}")

        self._logger.info("Successfully configured MCP tool servers for the agent")

    def _close_replaced_plugins(self, plugins: List[MCPStreamableHttpPlugin]) -> None:
        """Stop tracking MCP plugins an earlier call added and close them without delaying this turn.

        This also closes them for any ``Kernel.clone()`` copy that shares their functions; those
        copies carry the earlier turn's headers too.
        """
        replaced_ids = {id(plugin) for plugin in plugins}
        self._connected_plugins = [
            plugin for plugin in self._connected_plugins if id(plugin) not in replaced_ids
        ]
        for plugin in plugins:
            self._close_in_background(plugin)

    def _close_in_background(self, plugin: MCPStreamableHttpPlugin) -> None:
        """Close an MCP plugin in a task of its own; cleanup_connections() waits for it."""
        closing_task = _start_closing(plugin)
        self._pending_closes.add(closing_task)
        closing_task.add_done_callback(self._pending_closes.discard)

    # ============================================================================
    # Private Methods - Input Validation & Processing
    # ============================================================================

    def _validate_inputs(
        self, kernel: sk.Kernel, agentic_app_id: str, auth_token: Optional[str]
    ) -> None:
        """Validate all required inputs. In dev mode only kernel is checked."""
        if kernel is None:
            raise ValueError("kernel cannot be None")
        if is_development_environment():
            return
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
        """Close the MCP plugins this service connected.

        Also waits for the plugins that later calls replaced to finish closing.
        """
        plugins, self._connected_plugins = self._connected_plugins, []
        self._logger.info(f"Cleaning up {len(plugins)} MCP plugin connections")

        for plugin in plugins:
            try:
                if hasattr(plugin, "close"):
                    await plugin.close()
                elif hasattr(plugin, "disconnect"):
                    await plugin.disconnect()
                self._logger.debug(
                    f"Closed connection for plugin: {getattr(plugin, 'name', 'unknown')}"
                )
            except Exception as e:
                self._logger.warning(f"Error closing plugin connection: {e}")

        if self._pending_closes:
            _, still_closing = await asyncio.wait(
                set(self._pending_closes), timeout=_CLOSE_TIMEOUT_SECONDS
            )
            if still_closing:
                self._logger.warning(
                    f"{len(still_closing)} replaced MCP plugins did not finish closing within "
                    f"{_CLOSE_TIMEOUT_SECONDS} seconds"
                )
        self._logger.info("All MCP plugin connections cleaned up")

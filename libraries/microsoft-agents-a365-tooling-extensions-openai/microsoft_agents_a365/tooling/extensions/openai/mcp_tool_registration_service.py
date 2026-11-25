# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service for OpenAI.

This module provides OpenAI-specific extensions for MCP tool registration,
including methods to send chat history from OpenAI Sessions and message lists.
"""

import asyncio
import logging
import uuid
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from agents import Agent
from agents.items import TResponseInputItem
from agents.mcp import (
    MCPServer,
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
    is_development_environment,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPServerInfo:
    """Information about an MCP server"""

    name: str
    url: str
    server_type: str = "streamable_http"  # hosted, streamable_http, sse, stdio
    headers: Optional[Dict[str, str]] = None
    require_approval: str = "never"
    timeout: int = 30  # Timeout in seconds (will be converted to milliseconds for MCPServerStreamableHttpParams)


# MCP servers created by add_tool_servers_to_agent, mapped to the URL and the exact request
# headers (including the Authorization token) each one was connected with. Module-level so
# servers attached by any service instance are recognized; entries are dropped when the
# server object is garbage collected.
_sdk_managed_servers: "weakref.WeakKeyDictionary[MCPServer, Tuple[str, Dict[str, str]]]" = (
    weakref.WeakKeyDictionary()
)


def _get_sdk_managed_server_state(server: MCPServer) -> Optional[Tuple[str, Dict[str, str]]]:
    """Return the (url, headers) an SDK-created server was connected with, or None."""
    try:
        return _sdk_managed_servers.get(server)
    except TypeError:
        # Not hashable or weak-referenceable, so it was not created by this service.
        return None


class _DedicatedTaskMCPServer(MCPServerStreamableHttp):
    """MCPServerStreamableHttp that connects and disconnects in a task of its own.

    While connected, the MCP client keeps anyio task groups open in the task that called
    ``connect()``. Closing them from another task cancels that task, and a request that fails
    inside them (for example the server rejecting the session with HTTP 403) cancels it too.
    Opening and closing the connection in one dedicated task lets any task close the server,
    for example a later call that replaces it, without cancelling a turn that is still using it,
    and turns a failed connection into an ordinary exception for the caller. The server connects
    only once, so a server that has been closed stays closed.
    """

    def __init__(self, params: MCPServerStreamableHttpParams, name: Optional[str] = None) -> None:
        super().__init__(params=params, name=name)
        self._connection_task: Optional["asyncio.Task[None]"] = None
        self._connection_loop: Optional[asyncio.AbstractEventLoop] = None
        self._close_requested = asyncio.Event()

    @property
    def is_open(self) -> bool:
        """Whether the server is connected and has not been asked to close."""
        return (
            self.session is not None
            and self._connection_task is not None
            and not self._connection_task.done()
            and not self._close_requested.is_set()
        )

    async def connect(self) -> None:
        if self._connection_task is not None:
            raise RuntimeError(f"MCP server '{self.name}' can only be connected once")
        self._connection_loop = asyncio.get_running_loop()
        connected: "asyncio.Future[None]" = self._connection_loop.create_future()
        self._connection_task = asyncio.create_task(self._run_connection(connected))
        try:
            await asyncio.wait({connected})
        except asyncio.CancelledError:
            # The connection task closes the server once it is done connecting.
            self._close_requested.set()
            connected.add_done_callback(lambda future: future.cancelled() or future.exception())
            raise
        connected.result()

    async def _run_connection(self, connected: "asyncio.Future[None]") -> None:
        try:
            await super().connect()
        except BaseException as error:
            # A rejected session surfaces as cancellation of this task, so catch BaseException.
            if not connected.done():
                detail = f": {error}" if isinstance(error, Exception) else ""
                connected.set_exception(
                    ConnectionError(f"Failed to connect to MCP server '{self.name}'{detail}")
                )
            if not isinstance(error, (Exception, asyncio.CancelledError)):
                raise
        else:
            connected.set_result(None)
            await self._close_requested.wait()
        finally:
            await super().cleanup()

    async def cleanup(self) -> None:
        self._close_requested.set()
        connection_task = self._connection_task
        if connection_task is None or connection_task is asyncio.current_task():
            return
        await asyncio.wait({connection_task})
        if not connection_task.cancelled() and connection_task.exception() is not None:
            logging.getLogger(__name__).debug(
                f"MCP server '{self.name}' closed with error: {connection_task.exception()}"
            )


def _is_open(server: MCPServer) -> bool:
    """Return True if an MCP server is still connected."""
    is_open = getattr(server, "is_open", None)
    if isinstance(is_open, bool):
        return is_open
    return getattr(server, "session", None) is not None


class _AgentMcpServers(list):
    """The ``mcp_servers`` list of an agent that ``add_tool_servers_to_agent`` returned.

    ``Agent.clone()`` shares this list unless it is given new ``mcp_servers``, so the list lives
    as long as the agent or any of its clones. An SDK-created server is closed once no such list
    holds it any more, so its connection doesn't stay open after the agents using it are gone.
    """

    __slots__ = ("__weakref__",)


# How many live _AgentMcpServers lists hold each SDK-created server. A server that a later call
# reuses is held by the lists of both agents.
_server_list_counts: "weakref.WeakKeyDictionary[MCPServer, int]" = weakref.WeakKeyDictionary()

# Services whose cleanup_all_servers() closes each SDK-created server. A server that is closed
# because it was replaced, or because no agent holds it any more, is removed from them.
_server_trackers: "weakref.WeakKeyDictionary[MCPServer, weakref.WeakSet[object]]" = (
    weakref.WeakKeyDictionary()
)

# Background tasks closing servers that no agent holds any more; kept so they are not garbage
# collected before they finish.
_closing_tasks: "set[asyncio.Task[None]]" = set()


def _hold_servers(server_list: _AgentMcpServers) -> None:
    """Count the SDK-created servers in an agent's list, and release them when it's collected."""
    servers = {
        id(server): server
        for server in server_list
        if _get_sdk_managed_server_state(server) is not None
    }
    if not servers:
        return
    for server in servers.values():
        _server_list_counts[server] = _server_list_counts.get(server, 0) + 1
    # The finalizer must not refer to the list itself, or the list would never be collected.
    finalizer = weakref.finalize(
        server_list, _release_servers_soon, tuple(servers.values()), asyncio.get_running_loop()
    )
    finalizer.atexit = False


def _release_servers_soon(
    servers: Tuple[MCPServer, ...], fallback_loop: asyncio.AbstractEventLoop
) -> None:
    """Release the servers of a collected list on the event loops they connected on.

    This runs wherever garbage collection runs, possibly in another thread, so it only
    schedules the release.
    """
    servers_by_loop: "dict[asyncio.AbstractEventLoop, List[MCPServer]]" = {}
    for server in servers:
        loop = getattr(server, "_connection_loop", None) or fallback_loop
        servers_by_loop.setdefault(loop, []).append(server)
    for loop, loop_servers in servers_by_loop.items():
        try:
            loop.call_soon_threadsafe(_release_servers, loop_servers)
        except RuntimeError:
            # The event loop is closed, and the connections it ran were closed with it.
            pass


def _release_servers(servers: List[MCPServer]) -> None:
    """Close each server that no live agent list holds any more. Runs on the server's loop."""
    for server in servers:
        try:
            count = _server_list_counts.get(server, 0) - 1
            if count > 0:
                _server_list_counts[server] = count
                continue
            _server_list_counts.pop(server, None)
            _forget_server(server)
            if _is_open(server):
                logger.debug(f"Closing MCP server '{server.name}', which no agent uses any more")
                closing_task = asyncio.get_running_loop().create_task(_close_server(server))
                _closing_tasks.add(closing_task)
                closing_task.add_done_callback(_closing_tasks.discard)
        except Exception as error:
            logger.debug(f"Error releasing MCP server '{server.name}': {error}")


async def _close_server(server: MCPServer) -> None:
    """Close an MCP server, logging instead of raising if that fails."""
    try:
        await server.cleanup()
    except Exception as error:
        logger.debug(f"Error closing MCP server '{server.name}': {error}")


def _forget_server(server: MCPServer) -> None:
    """Stop tracking a server in every service whose cleanup_all_servers() would close it."""
    trackers = _server_trackers.pop(server, None)
    for service in list(trackers or ()):
        service._forget_servers([server])


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
        Add the MCP servers discovered for the current turn to the agent.

        Note: Due to OpenAI Agents SDK limitations, MCP servers must be set during
        Agent creation. Whenever the agent's MCP servers change, this method returns a
        copy of the agent (made with ``agent.clone``) instead of modifying it.

        Each MCP server carries the current caller's Authorization token in its request
        headers. A server attached by an earlier call is reused only when it is still connected
        and its URL and headers (including the token) are identical to this turn's. Every other
        server attached by an earlier call is closed, including when this method raises or is
        cancelled, so an agent from an earlier turn can no longer call MCP servers with that
        turn's token. When this method raises or is cancelled, it also removes those servers
        from the agent passed in (by assigning it a new ``mcp_servers`` list), so that agent can
        still run without them. Servers the caller configured on the agent are kept as-is. A
        server that fails to connect, for example because it rejects the caller, is skipped.

        Build the agent for each turn from a base agent without MCP servers from this method,
        use the returned agent only for that turn, and call ``cleanup_all_servers()`` when the
        turn ends. Use a separate service for each turn, because ``cleanup_all_servers()``
        closes the servers on every agent the service returned. Turns that run concurrently
        must not share an agent. If ``cleanup_all_servers()`` isn't called, each server this
        method connected is closed once the returned agent and all of its ``clone()`` copies
        have been garbage collected. This relies on the list that this method gives the agent
        as ``mcp_servers``, which ``clone()`` shares: an agent that holds these servers in a
        list of its own, for example ``agent.clone(mcp_servers=[...])``, doesn't keep them open.

        Args:
            agent: The existing agent to add servers to
            auth: Authorization handler for token exchange.
            auth_handler_name: Name of the authorization handler.
            context: Turn context for the current operation.
            auth_token: Authentication token to access the MCP servers.

        Returns:
            Copy of the agent with this turn's MCP servers, or the agent passed in if it already
            holds exactly this turn's servers in a list that this method returned.
        """
        # Get existing MCP servers from the agent
        existing_mcp_servers = (
            list(agent.mcp_servers) if hasattr(agent, "mcp_servers") and agent.mcp_servers else []
        )

        # Separate servers the caller configured from servers attached by an earlier call.
        # The latter carry the token of whichever user or agent identity that call ran for.
        caller_mcp_servers: List[MCPServer] = []
        previous_sdk_servers: List[MCPServer] = []
        previous_sdk_servers_by_url: Dict[str, Tuple[MCPServer, Dict[str, str]]] = {}
        for server in existing_mcp_servers:
            sdk_state = _get_sdk_managed_server_state(server)
            if sdk_state is None:
                caller_mcp_servers.append(server)
            else:
                previous_sdk_servers.append(server)
                previous_url, previous_headers = sdk_state
                previous_sdk_servers_by_url.setdefault(previous_url, (server, previous_headers))

        try:
            is_dev = is_development_environment()
            if (auth_token is None or auth_token.strip() == "") and not is_dev:
                # Only exchange a token in production; dev mode uses BEARER_TOKEN* env vars instead.
                scopes = get_mcp_platform_authentication_scope()
                authToken = await auth.exchange_token(context, scopes, auth_handler_name)
                auth_token = authToken.token

            options = ToolOptions(orchestrator_name=self._orchestrator_name)
            # In dev mode, agentic_app_id is not needed for manifest-based discovery.
            agentic_app_id = "" if is_dev else Utility.resolve_agent_identity(context, auth_token)
            self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")
            mcp_server_configs = await self.config_service.list_tool_servers(
                agentic_app_id=agentic_app_id,
                auth_token=auth_token,
                options=options,
                authorization=auth,
                auth_handler_name=auth_handler_name,
                turn_context=context,
            )
        except BaseException:
            # Also on cancellation: without this turn's servers, none from an earlier call may
            # stay usable. Leave the agent usable without them.
            self._remove_servers(agent, previous_sdk_servers)
            await self._close_replaced_servers(previous_sdk_servers)
            raise

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
                headers=dict(server_config.headers) if server_config.headers else None,
            )
            mcp_servers_info.append(server_info)

        # Servers the caller configured take precedence over discovered servers at the same URL.
        added_server_urls = set()
        for server in caller_mcp_servers:
            server_url = self._get_server_url(server)
            if server_url is not None:
                added_server_urls.add(server_url)

        sdk_mcp_servers: List[MCPServer] = []
        reused_servers: List[MCPServer] = []
        connected_servers: List[MCPServer] = []

        try:
            for si in mcp_servers_info:
                if si.url in added_server_urls:
                    continue

                try:
                    # Merge base headers with per-server headers from list_tool_servers.
                    # si.headers already contains the correct per-audience Authorization token.
                    base_headers = {
                        Constants.Headers.USER_AGENT: Utility.get_user_agent_header(
                            self._orchestrator_name
                        )
                    }
                    server_headers = dict(si.headers) if si.headers else {}
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
                    headers = {
                        **base_headers,
                        **server_headers,
                    }  # per-audience token takes precedence

                    # Identical headers mean the same token, and so the same identity: keep the
                    # existing connection while it is open. Any other previous server is
                    # replaced, never reused.
                    previous = previous_sdk_servers_by_url.get(si.url)
                    if previous is not None and previous[1] == headers and _is_open(previous[0]):
                        sdk_mcp_servers.append(previous[0])
                        reused_servers.append(previous[0])
                        added_server_urls.add(si.url)
                        self._logger.info(
                            f"Reusing MCP server '{si.name}' at {si.url}; credentials unchanged"
                        )
                        continue

                    # Create MCPServerStreamableHttpParams with proper configuration
                    params = MCPServerStreamableHttpParams(url=si.url, headers=headers)

                    # Create the MCP server. It connects and disconnects in a task of its own, so
                    # it can be closed from any task.
                    mcp_server = _DedicatedTaskMCPServer(params=params, name=si.name)

                    # CRITICAL: Connect the server before adding it to the agent
                    # This fixes the "Server not initialized. Make sure you call `connect()` first." error
                    # TODO: When App Manifest scenario lits up for onboarding agent, we need to pull a flag and disconnect if the flag is disabled.
                    await mcp_server.connect()

                    _sdk_managed_servers[mcp_server] = (si.url, dict(headers))
                    sdk_mcp_servers.append(mcp_server)
                    connected_servers.append(mcp_server)

                    added_server_urls.add(si.url)
                    self._logger.info(
                        f"Successfully connected to MCP server '{si.name}' at {si.url}"
                    )

                except Exception as e:
                    # Log the error but continue with other servers. Never fall back to a server
                    # from an earlier call: it may carry another identity's token.
                    self._logger.warning(
                        f"Failed to connect to MCP server {si.name} at {si.url}: {e}"
                    )
                    continue

            all_mcp_servers = caller_mcp_servers + sdk_mcp_servers
            if (
                len(all_mcp_servers) == len(existing_mcp_servers)
                and {id(server) for server in all_mcp_servers}
                == {id(server) for server in existing_mcp_servers}
                # SDK servers stay open only while a list this service returned holds them.
                and (not sdk_mcp_servers or isinstance(agent.mcp_servers, _AgentMcpServers))
            ):
                self._logger.info("Agent MCP servers are already current")
                self._track_servers(reused_servers)
                return agent

            # Close servers from an earlier call that this turn does not reuse, so an agent from
            # an earlier turn cannot keep calling MCP servers with that turn's token.
            reused_ids = {id(server) for server in reused_servers}
            await self._close_replaced_servers(
                [server for server in previous_sdk_servers if id(server) not in reused_ids]
            )

            # The OpenAI Agents SDK requires MCP servers to be set during agent creation
            self._logger.info(
                f"Recreating agent with {len(all_mcp_servers)} MCP servers "
                f"({len(connected_servers)} newly connected)"
            )
            try:
                # clone() keeps every other agent setting (guardrails, handoffs, hooks, and so on)
                server_list = _AgentMcpServers(all_mcp_servers)
                new_agent = agent.clone(mcp_servers=server_list)
                # Close the servers once neither the new agent nor any of its clones is in use.
                if new_agent.mcp_servers is server_list:
                    _hold_servers(server_list)
            except Exception as e:
                self._logger.error(f"Failed to recreate agent with new MCP servers: {e}")
                raise

        except BaseException:
            # Also on cancellation: close the servers this call connected and every server an
            # earlier call attached, so none of them stays open or usable, and leave the agent
            # usable without them.
            self._remove_servers(agent, previous_sdk_servers)
            await self._cleanup_servers(connected_servers)
            await self._close_replaced_servers(previous_sdk_servers)
            raise

        # Record the servers on the returned agent, so cleanup_all_servers() closes them.
        self._track_servers(connected_servers + reused_servers)
        self._logger.info(
            f"Agent recreated successfully with {len(all_mcp_servers)} total MCP servers"
        )
        # Return the new agent (caller needs to replace the old one)
        return new_agent

    def _track_servers(self, servers: List[MCPServer]) -> None:
        """Record MCP servers on an agent this service returned, so cleanup_all_servers() closes them.

        Servers that are no longer open are dropped, so a long-lived service doesn't keep them.
        """
        if not hasattr(self, "_connected_servers"):
            self._connected_servers = []
        self._connected_servers = [server for server in self._connected_servers if _is_open(server)]
        tracked_ids = {id(server) for server in self._connected_servers}
        for server in servers:
            if id(server) not in tracked_ids:
                tracked_ids.add(id(server))
                self._connected_servers.append(server)
            try:
                _server_trackers.setdefault(server, weakref.WeakSet()).add(self)
            except TypeError:
                # Not hashable or weak-referenceable, so it was not created by this service.
                pass

    def _forget_servers(self, servers: List[MCPServer]) -> None:
        """Stop tracking MCP servers, without changing a list that cleanup may be closing."""
        if not hasattr(self, "_connected_servers"):
            return
        forgotten_ids = {id(server) for server in servers}
        self._connected_servers = [
            server for server in self._connected_servers if id(server) not in forgotten_ids
        ]

    def _remove_servers(self, agent: Agent, servers: List[MCPServer]) -> None:
        """Remove MCP servers from an agent without changing a list that its clones may share."""
        if not servers:
            return
        removed_ids = {id(server) for server in servers}
        try:
            agent.mcp_servers = [
                server for server in agent.mcp_servers if id(server) not in removed_ids
            ]
        except Exception as e:
            self._logger.debug(f"Could not remove closed MCP servers from the agent: {e}")

    async def _close_replaced_servers(self, servers: List[MCPServer]) -> None:
        """Close MCP servers attached by an earlier call that the current turn does not reuse."""
        self._forget_servers(servers)
        for server in servers:
            _forget_server(server)
        open_servers = [server for server in servers if _is_open(server)]
        if not open_servers:
            return
        self._logger.warning(
            f"Closing {len(open_servers)} MCP servers attached by an earlier call that this turn "
            "does not reuse. Build the agent for each turn from a base agent without these "
            "servers and use the returned agent only for that turn."
        )
        await self._cleanup_servers(open_servers)

    @staticmethod
    def _get_server_url(server: MCPServer) -> Optional[str]:
        """Return the URL an MCP server connects to, if it exposes one."""
        params = getattr(server, "params", None)
        # MCPServerStreamableHttp stores the URL in params["url"]
        if isinstance(params, dict) and "url" in params:
            return params["url"]
        if params is not None and hasattr(params, "url"):
            return params.url
        return getattr(server, "url", None)

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
        """Close the MCP servers on every agent this service returned.

        Use one service per turn: this also closes servers that other turns using the same
        service are still working with.
        """
        if hasattr(self, "_connected_servers"):
            servers, self._connected_servers = self._connected_servers, []
            await self._cleanup_servers(servers)

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
                      message types. Can be empty - the request will still be sent to
                      register the user message from turn_context.activity.text.
            options: Optional ToolOptions for customization. If not provided,
                     uses default options with orchestrator_name="OpenAI".

        Returns:
            OperationResult indicating success or failure. On success, returns
            OperationResult.success(). On failure, returns OperationResult.failed()
            with error details.

        Raises:
            ValueError: If turn_context is None or messages is None.

        Note:
            Even if messages is empty or all messages are filtered during conversion,
            the request will still be sent to the MCP platform. This ensures the user
            message from turn_context.activity.text is registered correctly for
            real-time threat protection.

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

        self._logger.info(f"Sending {len(messages)} OpenAI messages as chat history")

        # Set default options
        if options is None:
            options = ToolOptions(orchestrator_name=self._orchestrator_name)
        elif options.orchestrator_name is None:
            options.orchestrator_name = self._orchestrator_name

        try:
            # Convert OpenAI messages to ChatHistoryMessage format
            chat_history_messages = self._convert_openai_messages_to_chat_history(messages)

            # Call core service even with empty chat_history_messages to register
            # the user message from turn_context.activity.text in the MCP platform.
            if len(chat_history_messages) == 0:
                self._logger.info(
                    "Empty chat history messages (either no input or all filtered), "
                    "still sending to register user message"
                )

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

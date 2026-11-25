# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Tool Registration Service for Google ADK.

This service provides MCP (Model Context Protocol) tool registration
capabilities for Google ADK-based agents.
"""

# Standard library imports
import asyncio
import logging
import weakref
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

logger = logging.getLogger(__name__)

# MCP toolsets created by add_tool_servers_to_agent. Module-level so toolsets attached by
# any service instance are recognized; entries are dropped when the toolset is garbage
# collected.
_sdk_managed_toolsets: "weakref.WeakSet[McpToolset]" = weakref.WeakSet()

# Background tasks that close toolsets replaced by a later call, or whose agent is gone; kept so
# they are not garbage collected before they finish.
_closing_tasks: "set[asyncio.Task[None]]" = set()


def _is_sdk_managed_toolset(tool: object) -> bool:
    """Return True if the tool is an MCP toolset created by this service."""
    try:
        return tool in _sdk_managed_toolsets
    except TypeError:
        # Not hashable or weak-referenceable, so it was not created by this service.
        return False


class _AgentScope:
    """The MCP toolsets added to one agent, each with the event loop it was added on.

    They are closed once the agent is garbage collected.
    """

    __slots__ = ("agent_ref", "toolsets")

    def __init__(self, agent_ref: "weakref.ref[Agent]") -> None:
        self.agent_ref = agent_ref
        self.toolsets: "dict[int, tuple[McpToolset, asyncio.AbstractEventLoop]]" = {}


# The MCP toolsets that add_tool_servers_to_agent added to each live agent, keyed by id(agent)
# because agents are unhashable. An entry is removed when its agent is garbage collected.
_agent_scopes: "dict[int, _AgentScope]" = {}

# Services whose cleanup() closes each MCP toolset. A toolset that is closed because it was
# replaced, or because its agent is gone, is removed from them.
_toolset_trackers: "weakref.WeakKeyDictionary[McpToolset, weakref.WeakSet[object]]" = (
    weakref.WeakKeyDictionary()
)


def _agent_scope(agent: Agent, create: bool) -> Optional[_AgentScope]:
    """Return the toolsets added to an agent, creating the record (and its finalizer) if asked."""
    scope = _agent_scopes.get(id(agent))
    if scope is not None and scope.agent_ref() is agent:
        return scope
    if not create:
        return None
    try:
        agent_ref = weakref.ref(agent)
    except TypeError:
        return None
    scope = _AgentScope(agent_ref)
    _agent_scopes[id(agent)] = scope
    # The finalizer must not refer to the agent itself, or the agent would never be collected.
    finalizer = weakref.finalize(agent, _release_agent_scope_soon, id(agent), scope)
    finalizer.atexit = False
    return scope


def _release_agent_scope_soon(key: int, scope: _AgentScope) -> None:
    """Close the toolsets of a collected agent on the event loops they were added on.

    This runs wherever garbage collection runs, possibly in another thread, so it only
    schedules the closes.
    """
    if _agent_scopes.get(key) is scope:
        _agent_scopes.pop(key, None)
    toolsets_by_loop: "dict[asyncio.AbstractEventLoop, List[McpToolset]]" = {}
    for toolset, loop in list(scope.toolsets.values()):
        toolsets_by_loop.setdefault(loop, []).append(toolset)
    scope.toolsets.clear()
    for loop, toolsets in toolsets_by_loop.items():
        try:
            loop.call_soon_threadsafe(_close_released_toolsets, toolsets)
        except RuntimeError:
            # The event loop is closed, and the sessions it ran were closed with it.
            pass


def _close_released_toolsets(toolsets: List[McpToolset]) -> None:
    """Close MCP toolsets whose agent is gone. Runs on the loop they were added on."""
    for toolset in toolsets:
        _forget_toolset(toolset)
    closing_task = asyncio.get_running_loop().create_task(_close_toolsets(toolsets))
    _closing_tasks.add(closing_task)
    closing_task.add_done_callback(_closing_tasks.discard)


async def _close_toolsets(toolsets: List[McpToolset]) -> None:
    """Close MCP toolsets, logging instead of raising if that fails."""
    for toolset in toolsets:
        try:
            await toolset.close()
        except Exception as close_ex:
            logger.debug(f"Error closing an MCP toolset: {close_ex}")


def _forget_toolset(toolset: McpToolset) -> None:
    """Stop tracking an MCP toolset in every service whose cleanup() would close it."""
    trackers = _toolset_trackers.pop(toolset, None)
    for service in list(trackers or ()):
        service._forget_toolsets([toolset])


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
        # Background closes of toolsets replaced by a later call; cleanup() waits for them.
        self._pending_closes: "set[asyncio.Task[None]]" = set()

    async def add_tool_servers_to_agent(
        self,
        agent: Agent,
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
        auth_token: Optional[str] = None,
    ) -> None:
        """
        Add the MCP servers discovered for the current turn to the agent.

        Note: Modifies the provided agent in place to add new MCP tool servers.

        Each MCP toolset carries the current caller's Authorization token in its request
        headers. Toolsets attached by an earlier call are removed from the agent before
        anything else happens and closed in the background, and fresh toolsets are created for
        this turn. An agent that is reused from one turn to the next therefore does not keep
        toolsets that carry an earlier turn's headers, even if this call fails. Tools the
        caller configured on the agent are kept as-is.

        Turns that run at the same time must not share an agent: each call replaces the agent's
        toolsets and closes the ones it replaces, which ends any other turn that is still using
        them. Give each turn its own agent, for example a ``clone()`` of a base agent without
        these toolsets.

        Use a separate service for each turn and call ``cleanup()`` in a ``finally`` block when
        the turn ends; it closes every toolset the service created, so on a shared service it
        would also end other turns. If ``cleanup()`` isn't called, the toolsets are closed once
        the agent they were added to has been garbage collected. An agent that these toolsets
        are copied into, for example by ``clone()`` after this call, doesn't keep them open, so
        clone the base agent before calling this method rather than after.

        Example:
            >>> service = McpToolRegistrationService()
            >>> agent = base_agent.clone()
            >>> try:
            ...     await service.add_tool_servers_to_agent(agent, auth, "agentic", turn_context)
            ...     async for event in Runner(agent=agent, ...).run_async(...):
            ...         ...
            ... finally:
            ...     await service.cleanup()

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
        # Remove toolsets attached by an earlier call before anything here can fail. They carry
        # the headers of the turn that created them.
        previous_tools = list(agent.tools) if agent.tools else []
        caller_tools = [tool for tool in previous_tools if not _is_sdk_managed_toolset(tool)]
        if len(caller_tools) != len(previous_tools):
            agent.tools = caller_tools
            self._logger.info(
                f"Removed {len(previous_tools) - len(caller_tools)} MCP toolsets "
                "attached by an earlier call"
            )
            self._close_replaced_toolsets(
                agent, [tool for tool in previous_tools if _is_sdk_managed_toolset(tool)]
            )

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

        # Collect URLs of MCP servers the caller configured; they take precedence over
        # discovered servers at the same URL (use set for O(1) lookup)
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

                _sdk_managed_toolsets.add(server_info)
                mcp_servers_info.append(server_info)
                self._track_toolset(server_info)
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
            # Close them once the agent is garbage collected, if cleanup() hasn't.
            scope = _agent_scope(agent, create=True)
            if scope is not None:
                loop = asyncio.get_running_loop()
                for toolset in mcp_servers_info:
                    scope.toolsets[id(toolset)] = (toolset, loop)
            self._logger.info(
                f"Successfully configured agent with {len(mcp_servers_info)} new MCP tool servers "
                f"(total tools: {len(all_tools)})"
            )
        else:
            self._logger.info("No new MCP servers to add to agent")

    def _close_replaced_toolsets(self, agent: Agent, toolsets: List[McpToolset]) -> None:
        """Release toolsets an earlier call attached, closing them without delaying this turn."""
        scope = _agent_scope(agent, create=False)
        for toolset in toolsets:
            if scope is not None:
                scope.toolsets.pop(id(toolset), None)
            _forget_toolset(toolset)
        self._forget_toolsets(toolsets)
        closing_task = asyncio.ensure_future(_close_toolsets(toolsets))
        for tasks in (_closing_tasks, self._pending_closes):
            tasks.add(closing_task)
            closing_task.add_done_callback(tasks.discard)

    def _track_toolset(self, toolset: McpToolset) -> None:
        """Record an MCP toolset added to an agent, so cleanup() closes it."""
        self._connected_servers.append(toolset)
        try:
            _toolset_trackers.setdefault(toolset, weakref.WeakSet()).add(self)
        except TypeError:
            # Not hashable or weak-referenceable, so it can only be closed by this service.
            pass

    def _forget_toolsets(self, toolsets: List[McpToolset]) -> None:
        """Stop tracking MCP toolsets, without changing a list that cleanup may be closing."""
        forgotten_ids = {id(toolset) for toolset in toolsets}
        self._connected_servers = [
            toolset for toolset in self._connected_servers if id(toolset) not in forgotten_ids
        ]

    async def cleanup(self):
        """Close the MCP toolsets this service created.

        Also waits for the toolsets that later calls replaced to finish closing. Use one
        service per turn and call this in a ``finally`` block when the turn ends: it also
        closes toolsets that other turns using the same service are still working with.
        Toolsets that are not closed this way are closed once the agent they were added to is
        gone.
        """
        try:
            toolsets, self._connected_servers = self._connected_servers, []
            for toolset in toolsets:
                try:
                    if hasattr(toolset, "close"):
                        await toolset.close()
                except Exception as cleanup_ex:
                    self._logger.debug(f"Error during cleanup: {cleanup_ex}")
            # Also wait for the toolsets that later calls replaced to finish closing.
            if self._pending_closes:
                await asyncio.wait(set(self._pending_closes))
        except Exception as ex:
            self._logger.debug(f"Error during service cleanup: {ex}")

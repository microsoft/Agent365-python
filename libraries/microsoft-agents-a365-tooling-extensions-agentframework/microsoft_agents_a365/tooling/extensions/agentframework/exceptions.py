# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Exceptions raised by the Agent Framework MCP tooling extension."""

from typing import List, Optional


class McpConnectionsRequiredError(Exception):
    """Raised when one or more configured MCP servers are not yet connection-ready.

    The tooling gateway reports a per-server ``connectivityStatus`` of ``"Pending"``
    when an MCP server has downstream connections the user has not yet established.
    ``McpToolRegistrationService.add_tool_servers_to_agent`` discovers the servers
    every turn and raises this error *before* building the agent when any server is
    Pending, so the agent's turn handler can catch it, reply to the user with
    ``all_connections_url``, and return without running the model/tools. A later turn
    re-runs discovery and proceeds once the connections are in place.

    The error is raised at agent-construction time (not from inside a tool call) so it
    propagates to the developer's turn handler intact — Agent Framework's tool-call loop
    swallows exceptions raised inside a ``FunctionTool`` and reflects them to the model
    as an opaque error string, which would drop the setup URL.

    ``all_connections_url`` lets the user view and manage the full set of connectors
    required by the affected servers — including ones already set up — rather than being
    scoped strictly to the ones that happen to be missing right now.
    """

    def __init__(
        self,
        all_connections_url: Optional[str],
        connectivity_status: Optional[str],
        server_names: List[str],
    ) -> None:
        self.all_connections_url = all_connections_url
        self.connectivity_status = connectivity_status
        self.server_names = server_names
        servers_text = ", ".join(server_names) if server_names else "(unknown)"
        super().__init__(
            f"MCP servers [{servers_text}] require connection setup "
            f"(connectivityStatus={connectivity_status}). "
            f"Set up connections at: {all_connections_url}"
        )

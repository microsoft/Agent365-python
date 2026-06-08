# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Exceptions raised by the MCP tooling layer."""

from typing import List, Optional


class McpConnectionsRequiredError(Exception):
    """Raised when one or more configured MCP servers are not yet connection-ready.

    The tooling gateway reports an aggregate ``connectivityStatus`` of ``"Pending"``
    when the agent's MCP servers have downstream connections that the user has not yet
    established. The agent's turn handler should catch this error, reply to the user
    with ``missing_connections_url``, and return without running the model/tools.
    A later turn re-runs discovery and proceeds once the connections are in place.
    """

    def __init__(
        self,
        missing_connections_url: Optional[str],
        all_connections_url: Optional[str],
        connectivity_status: Optional[str],
        server_names: List[str],
    ) -> None:
        self.missing_connections_url = missing_connections_url
        self.all_connections_url = all_connections_url
        self.connectivity_status = connectivity_status
        self.server_names = server_names
        servers_text = ", ".join(server_names) if server_names else "(unknown)"
        super().__init__(
            f"MCP servers [{servers_text}] require connection setup "
            f"(connectivityStatus={connectivity_status}). "
            f"Set up missing connections at: {missing_connections_url}"
        )

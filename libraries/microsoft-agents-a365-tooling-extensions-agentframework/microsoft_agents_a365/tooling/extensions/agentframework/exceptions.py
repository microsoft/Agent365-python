# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Exceptions and message helpers for the Agent Framework MCP tooling extension."""

from typing import List, Optional


def format_mcp_connections_required_message(
    *,
    server_names: List[str],
    connectivity_status: Optional[str],
    missing_connections_url: Optional[str],
) -> str:
    """Build the static, user-facing message shown when an MCP server needs connection setup.

    This single helper is the source of truth for the wording so that the message a Pending
    server's placeholder tool returns to the model is identical to the message carried by
    ``McpConnectionsRequiredError``.

    Args:
        server_names: Names of the MCP server(s) whose downstream connections are not set up.
        connectivity_status: The gateway-reported ``connectivityStatus`` (typically ``"Pending"``).
        missing_connections_url: URL the user opens to set up the missing connection(s). May be
            ``None`` when the gateway did not supply one.

    Returns:
        A human-readable message suitable for relaying verbatim to the end user.
    """
    servers_text = ", ".join(server_names) if server_names else "(unknown)"
    message = (
        f"The tool(s) from MCP server(s) [{servers_text}] can't be used yet because the "
        f"required data connection(s) aren't set up (connectivityStatus={connectivity_status})."
    )
    if missing_connections_url:
        message += f" Set up the missing connection(s) here: {missing_connections_url}"
    else:
        message += " Ask your administrator to set up the required connection(s)."
    return message


class McpConnectionsRequiredError(Exception):
    """Raised when an MCP server the user invoked is not yet connection-ready.

    The tooling gateway reports a per-server ``connectivityStatus`` of ``"Pending"`` when an MCP
    server has downstream connections the user has not yet established. Discovery runs every turn.

    The agentframework extension gates **per server, non-blocking**: Ready servers are wired as
    real tools and a Pending server is registered as a placeholder tool. Only when the model
    actually invokes that placeholder (because the user's request needs the server) is the static
    setup message — including ``missing_connections_url`` — surfaced; the rest of the turn runs
    normally with the Ready tools.

    This exception is **not** raised by the non-blocking gate (Agent Framework swallows exceptions
    raised inside a tool, and converts ``UserInputRequiredException`` into tool-result content, so
    neither reaches the developer's turn handler). It is exported for developers who want to
    implement their own *blocking* gating — e.g. inspect the discovered servers and raise this
    before building the agent to abort the whole turn — and as the structured carrier of the same
    message the placeholder returns.
    """

    def __init__(
        self,
        missing_connections_url: Optional[str],
        connectivity_status: Optional[str],
        server_names: List[str],
    ) -> None:
        self.missing_connections_url = missing_connections_url
        self.connectivity_status = connectivity_status
        self.server_names = server_names
        super().__init__(
            format_mcp_connections_required_message(
                server_names=server_names,
                connectivity_status=connectivity_status,
                missing_connections_url=missing_connections_url,
            )
        )

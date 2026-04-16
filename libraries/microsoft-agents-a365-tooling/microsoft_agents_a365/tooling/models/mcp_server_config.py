# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Server Configuration model.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MCPServerConfig:
    """
    Represents the configuration for an MCP server, including its name and endpoint.
    """

    #: Gets or sets the name of the MCP server.
    mcp_server_name: str

    #: Gets or sets the unique name of the MCP server.
    mcp_server_unique_name: str

    #: Gets or sets the custom URL for the MCP server. If provided, this URL will be used
    #: instead of constructing the URL from the base URL and unique name.
    url: Optional[str] = None

    #: Per-server HTTP headers (includes the Authorization header set by attach_per_audience_tokens).
    headers: Optional[Dict[str, str]] = None

    #: Per-server AppId (V2) or shared ATG AppId (V1). None means treat as V1.
    audience: Optional[str] = None

    #: OAuth scope, e.g. "Tools.ListInvoke.All" (V2) or "McpServers.Mail.All" (V1).
    scope: Optional[str] = None

    #: Publisher identifier for the MCP server.
    publisher: Optional[str] = None

    def __post_init__(self):
        """Validate the configuration after initialization."""
        if not self.mcp_server_name:
            raise ValueError("mcp_server_name cannot be empty")
        if not self.mcp_server_unique_name:
            raise ValueError("mcp_server_unique_name cannot be empty")

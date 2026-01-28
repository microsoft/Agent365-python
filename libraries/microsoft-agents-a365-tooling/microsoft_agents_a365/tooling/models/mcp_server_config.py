# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP Server Configuration model.
"""

from dataclasses import dataclass
from typing import Optional


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

    def __post_init__(self):
        """Validate the configuration after initialization."""
        if not self.mcp_server_name:
            raise ValueError("mcp_server_name cannot be empty")
        if not self.mcp_server_unique_name:
            raise ValueError("mcp_server_unique_name cannot be empty")

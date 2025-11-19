# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Operation source enumeration for Agent365 SDK."""

from enum import Enum


class OperationSource(Enum):
    """
    Enumeration representing the source of an operation.
    """

    SDK = "SDK"
    """Operation executed by SDK."""

    GATEWAY = "Gateway"
    """Operation executed by Gateway."""

    MCP_SERVER = "MCPServer"
    """Operation executed by MCP Server."""

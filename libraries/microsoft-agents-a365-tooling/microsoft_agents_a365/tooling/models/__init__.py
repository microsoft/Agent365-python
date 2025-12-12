# Copyright (c) Microsoft. All rights reserved.

"""
Common models for MCP tooling.

This module defines data models used across the MCP tooling framework.
"""

from .mcp_server_config import MCPServerConfig
from .tool_options import ToolOptions

__all__ = ["MCPServerConfig", "ToolOptions"]

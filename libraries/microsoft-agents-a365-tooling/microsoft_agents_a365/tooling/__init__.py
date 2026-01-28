# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Microsoft Agent 365 Tooling SDK

Core tooling functionality shared across different AI frameworks.
Provides base utilities and common helper functions.
"""

from .models import MCPServerConfig
from .services import McpToolServerConfigurationService
from .utils import Constants
from .utils.utility import (
    get_tooling_gateway_for_digital_worker,
    get_mcp_base_url,
    build_mcp_server_url,
)

__version__ = "1.0.0"

__all__ = [
    "MCPServerConfig",
    "McpToolServerConfigurationService",
    "Constants",
    "get_tooling_gateway_for_digital_worker",
    "get_mcp_base_url",
    "build_mcp_server_url",
]

# Enable namespace package extension for tooling-extensions-* packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

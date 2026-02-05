# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Google ADK extensions for Microsoft Agent 365 Tooling SDK

Google ADK (Agent Development Kit) specific tools and services for AI agent development.
Provides MCP (Model Context Protocol) tool registration service for dynamically
adding MCP servers to Google ADK-based agents.

Main Service:
- McpToolRegistrationService: Add MCP tool servers to Google ADK agents

This module includes implementations for:
- Google ADK agent creation with MCP (Model Context Protocol) server support
- MCP tool registration service for dynamically adding MCP servers to agents
- Authentication and authorization patterns for MCP server discovery
"""

__version__ = "1.0.0"

# Import services from the services module
from .services import McpToolRegistrationService

__all__ = [
    "McpToolRegistrationService",
]

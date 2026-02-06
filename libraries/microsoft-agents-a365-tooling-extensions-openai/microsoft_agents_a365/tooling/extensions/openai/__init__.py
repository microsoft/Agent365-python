# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
OpenAI extensions for Microsoft Agent 365 Tooling SDK.

Tooling and utilities specifically for OpenAI framework integration.
Provides OpenAI-specific helper utilities including:
- McpToolRegistrationService: Service for MCP tool registration and chat history management

For type hints, use the types directly from the OpenAI Agents SDK:
- agents.memory.Session: Protocol for session objects
- agents.items.TResponseInputItem: Type for input message items
"""

from .mcp_tool_registration_service import McpToolRegistrationService

__version__ = "1.0.0"

__all__ = [
    "McpToolRegistrationService",
]

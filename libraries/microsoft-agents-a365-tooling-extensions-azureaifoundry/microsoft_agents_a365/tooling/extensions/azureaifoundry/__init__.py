# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure AI Foundry extension for Microsoft Agent 365 Tooling SDK

Azure AI Foundry specific tools and services for AI agent development.
Provides Azure AI Foundry-specific implementations and utilities for
building agents with Azure AI Foundry capabilities.
"""

__version__ = "1.0.0"

# Import services
from .services import (
    McpToolRegistrationService,
)

__all__ = [
    "McpToolRegistrationService",
]

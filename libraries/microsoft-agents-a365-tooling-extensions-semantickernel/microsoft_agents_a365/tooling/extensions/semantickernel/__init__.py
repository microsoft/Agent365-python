# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Semantic Kernel extensions for Microsoft Agent 365 Tooling SDK

Tooling and utilities specifically for Semantic Kernel framework integration.
Provides Semantic Kernel-specific helper utilities.
"""

from .services import McpToolRegistrationService

__version__ = "1.0.0"

__all__ = [
    "McpToolRegistrationService",
]

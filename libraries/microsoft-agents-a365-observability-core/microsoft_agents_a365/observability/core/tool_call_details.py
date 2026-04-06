# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Data class for tool call details.

from __future__ import annotations

from dataclasses import dataclass

from .models.service_endpoint import ServiceEndpoint


@dataclass
class ToolCallDetails:
    """Details of a tool call made by an agent in the system."""

    tool_name: str
    arguments: dict[str, object] | str | None = None
    tool_call_id: str | None = None
    description: str | None = None
    tool_type: str | None = None
    endpoint: ServiceEndpoint | None = None

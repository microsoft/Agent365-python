# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Data class for tool call details.

from dataclasses import dataclass
from urllib.parse import ParseResult


@dataclass
class ToolCallDetails:
    """Details of a tool call made by an agent in the system."""

    tool_name: str
    arguments: str | None = None
    tool_call_id: str | None = None
    description: str | None = None
    tool_type: str | None = None
    endpoint: ParseResult | None = None

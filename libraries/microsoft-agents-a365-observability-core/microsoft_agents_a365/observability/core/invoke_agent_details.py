# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Data class for invoke agent details.

from dataclasses import dataclass
from urllib.parse import ParseResult

from .agent_details import AgentDetails


@dataclass
class InvokeAgentDetails:
    """Details for agent invocation tracing."""

    details: AgentDetails
    endpoint: ParseResult | None = None
    session_id: str | None = None

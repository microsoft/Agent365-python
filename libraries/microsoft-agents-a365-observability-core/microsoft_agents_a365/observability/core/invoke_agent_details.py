# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Data class for invoke agent scope details.

from dataclasses import dataclass
from urllib.parse import ParseResult


@dataclass
class InvokeAgentScopeDetails:
    """Scope-level configuration for agent invocation tracing."""

    endpoint: ParseResult | None = None

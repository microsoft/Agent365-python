# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Data class for invoke agent scope details.

from dataclasses import dataclass

from .models.service_endpoint import ServiceEndpoint


@dataclass
class InvokeAgentScopeDetails:
    """Scope-level configuration for agent invocation tracing."""

    endpoint: ServiceEndpoint | None = None

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Microsoft Agent 365 Observability Hosting Library.
"""

from .middleware.baggage_middleware import BaggageMiddleware
from .middleware.observability_hosting_manager import (
    ObservabilityHostingManager,
    ObservabilityHostingOptions,
)
from .middleware.output_logging_middleware import A365_PARENT_SPAN_KEY, OutputLoggingMiddleware

__all__ = [
    "BaggageMiddleware",
    "OutputLoggingMiddleware",
    "A365_PARENT_SPAN_KEY",
    "ObservabilityHostingManager",
    "ObservabilityHostingOptions",
]

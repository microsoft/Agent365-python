# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Trace Processors
"""

from .span_processor import SpanProcessor

# Export public API
__all__ = [
    # Span processor
    "SpanProcessor",
]

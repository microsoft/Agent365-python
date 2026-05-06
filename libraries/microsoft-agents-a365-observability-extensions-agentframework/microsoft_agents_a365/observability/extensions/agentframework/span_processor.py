# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from opentelemetry.sdk.trace.export import SpanProcessor


class AgentFrameworkSpanProcessor(SpanProcessor):
    """SpanProcessor for Agent Framework.

    Attribute mutation happens in the enricher (via :class:`EnrichedReadableSpan`)
    because OTel Python ``ReadableSpan`` is immutable after ``on_end``.
    The enricher is invoked at export time by the ``EnrichingSpanProcessor``.
    """

    def __init__(self, service_name: str | None = None):
        self.service_name = service_name
        super().__init__()

    def on_start(self, span, parent_context):
        """Called when a span starts. Intentionally a no-op."""
        pass

    def on_end(self, span):
        """Called when a span ends. Intentionally a no-op.

        Message mapping is handled by the span enricher at export time
        since ReadableSpan is immutable in the Python OTel SDK.
        """
        pass

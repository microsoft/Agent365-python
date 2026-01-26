# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Span enrichment support for the Agent365 exporter pipeline."""

import threading
from collections.abc import Callable

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Registry for span enrichers - allows extensions to add attributes to spans before export
_span_enrichers: list[Callable[[ReadableSpan], ReadableSpan]] = []
_enrichers_lock = threading.Lock()


def register_span_enricher(enricher: Callable[[ReadableSpan], ReadableSpan]) -> None:
    """
    Register a function that enriches spans before export.

    Extensions (like Semantic Kernel, LangChain, etc.) can register enrichers
    that modify spans before they are exported by the BatchSpanProcessor.

    Args:
        enricher: A function that takes a ReadableSpan and returns an
                  enriched ReadableSpan (or the same span if no changes).
    """
    with _enrichers_lock:
        if enricher not in _span_enrichers:
            _span_enrichers.append(enricher)


def unregister_span_enricher(enricher: Callable[[ReadableSpan], ReadableSpan]) -> None:
    """
    Remove a previously registered enricher.

    Args:
        enricher: The enricher function to remove.
    """
    with _enrichers_lock:
        if enricher in _span_enrichers:
            _span_enrichers.remove(enricher)


class _EnrichingBatchSpanProcessor(BatchSpanProcessor):
    """
    BatchSpanProcessor that applies registered enrichers before export.

    This allows extensions to modify spans after they end but before
    they are batched and exported.
    """

    def on_end(self, span: ReadableSpan) -> None:
        """
        Apply all registered enrichers to the span before batching.

        Args:
            span: The ReadableSpan that has ended.
        """
        enriched_span = span
        with _enrichers_lock:
            enrichers = list(_span_enrichers)  # Copy to avoid holding lock during enrichment

        for enricher in enrichers:
            try:
                enriched_span = enricher(enriched_span)
            except Exception:
                # Don't let enrichment failures break the pipeline
                pass

        super().on_end(enriched_span)

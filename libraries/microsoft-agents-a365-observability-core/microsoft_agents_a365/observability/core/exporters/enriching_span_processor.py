# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Span enrichment support for the Agent365 exporter pipeline."""

import logging
import threading
from collections.abc import Callable

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

# Single span enricher - only one platform instrumentor should be active at a time
_span_enricher: Callable[[ReadableSpan], ReadableSpan] | None = None
_enricher_lock = threading.Lock()


def register_span_enricher(enricher: Callable[[ReadableSpan], ReadableSpan]) -> None:
    """Register the span enricher for the active platform instrumentor.

    Only one enricher can be registered at a time since auto-instrumentation
    is platform-specific (Semantic Kernel, LangChain, or OpenAI Agents).

    Args:
        enricher: Function that takes a ReadableSpan and returns an enriched span.

    Raises:
        RuntimeError: If an enricher is already registered.
    """
    global _span_enricher
    with _enricher_lock:
        if _span_enricher is not None:
            raise RuntimeError(
                "A span enricher is already registered. "
                "Only one platform instrumentor can be active at a time."
            )
        _span_enricher = enricher
        logger.debug("Span enricher registered: %s", enricher.__name__)


def unregister_span_enricher() -> None:
    """Unregister the current span enricher.

    Called during uninstrumentation to clean up.
    """
    global _span_enricher
    with _enricher_lock:
        if _span_enricher is not None:
            logger.debug("Span enricher unregistered: %s", _span_enricher.__name__)
            _span_enricher = None


def get_span_enricher() -> Callable[[ReadableSpan], ReadableSpan] | None:
    """Get the currently registered span enricher.

    Returns:
        The registered enricher function, or None if no enricher is registered.
    """
    with _enricher_lock:
        return _span_enricher


class _EnrichingBatchSpanProcessor(BatchSpanProcessor):
    """BatchSpanProcessor that applies the registered enricher before batching."""

    def on_end(self, span: ReadableSpan) -> None:
        """Apply the span enricher and pass to parent for batching.

        Args:
            span: The span that has ended.
        """
        enriched_span = span

        enricher = get_span_enricher()
        if enricher is not None:
            try:
                enriched_span = enricher(span)
            except Exception:
                logger.exception(
                    "Span enricher %s raised an exception, using original span",
                    enricher.__name__,
                )

        super().on_end(enriched_span)

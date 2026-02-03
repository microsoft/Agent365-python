# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from microsoft_agents_a365.observability.core.config import (
    get_tracer_provider,
    is_configured,
)
from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    register_span_enricher,
    unregister_span_enricher,
)
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

from microsoft_agents_a365.observability.extensions.semantickernel.span_enricher import (
    enrich_semantic_kernel_span,
)
from microsoft_agents_a365.observability.extensions.semantickernel.span_processor import (
    SemanticKernelSpanProcessor,
)

_instruments = ("semantic-kernel >= 1.0.0",)


class SemanticKernelInstrumentor(BaseInstrumentor):
    """
    Instruments Semantic Kernel with Agent365 observability.
    """

    def __init__(self):
        if not is_configured():
            raise RuntimeError(
                "Microsoft Agent 365 is not initialized. Call configure() before instrumenting."
            )
        super().__init__()

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """
        Instrument Semantic Kernel.

        Args:
            **kwargs: Optional configuration parameters.
        """
        provider = get_tracer_provider()

        # Add processor for on_start modifications (rename spans, add attributes)
        self._processor = SemanticKernelSpanProcessor()
        provider.add_span_processor(self._processor)

        # Register enricher for on_end modifications
        # This enricher runs before the span is exported, allowing us to
        # transform SK-specific attributes to standard gen_ai attributes
        register_span_enricher(enrich_semantic_kernel_span)

    def _uninstrument(self, **kwargs: Any) -> None:
        """
        Remove Semantic Kernel instrumentation.

        Args:
            **kwargs: Optional configuration parameters.
        """
        # Unregister the enricher
        unregister_span_enricher()

        # Shutdown the processor
        if hasattr(self, "_processor"):
            self._processor.shutdown()

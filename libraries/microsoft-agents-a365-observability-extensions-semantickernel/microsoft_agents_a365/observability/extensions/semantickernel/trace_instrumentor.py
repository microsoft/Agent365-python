# Copyright (c) Microsoft. All rights reserved.

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from microsoft_agents_a365.observability.core.config import get_tracer_provider, is_configured
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

from microsoft_agents_a365.observability.extensions.semantickernel.span_processor import (
    SemanticKernelSpanProcessor,
)

# -----------------------------
# 3) The Instrumentor class
# -----------------------------
_instruments = ("semantic-kernel >= 1.0.0",)


class SemanticKernelInstrumentor(BaseInstrumentor):
    """
    Instruments Semantic Kernel:
      • Installs your custom OTel SpanProcessor
      • (Optionally) attaches an SK function-invocation filter to enrich spans
    """

    def __init__(self):
        if not is_configured():
            raise RuntimeError(
                "Microsoft Agent 365 (or your telemetry config) is not initialized. Configure it before instrumenting."
            )
        super().__init__()

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """
        kwargs (all optional):
        """

        # Ensure we have an SDK TracerProvider
        provider = get_tracer_provider()
        self._processor = SemanticKernelSpanProcessor()
        provider.add_span_processor(self._processor)

    def _uninstrument(self, **kwargs: Any) -> None:
        pass

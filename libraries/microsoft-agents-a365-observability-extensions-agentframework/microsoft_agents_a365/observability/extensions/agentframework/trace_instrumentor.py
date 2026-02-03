# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from microsoft_agents_a365.observability.core.config import get_tracer_provider, is_configured
from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    register_span_enricher,
    unregister_span_enricher,
)
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

from microsoft_agents_a365.observability.extensions.agentframework.span_enricher import (
    enrich_agent_framework_span,
)
from microsoft_agents_a365.observability.extensions.agentframework.span_processor import (
    AgentFrameworkSpanProcessor,
)

# -----------------------------
# 3) The Instrumentor class
# -----------------------------
_instruments = ("agent-framework-azure-ai >= 1.0.0",)


class AgentFrameworkInstrumentor(BaseInstrumentor):
    """
    Instruments Agent Framework with Agent365 observability.
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
        Instrument Agent Framework.

        Args:
            **kwargs: Optional configuration parameters.
        """
        # Ensure we have an SDK TracerProvider
        provider = get_tracer_provider()

        # Add processor for on_start modifications (rename spans, add attributes)
        self._processor = AgentFrameworkSpanProcessor()
        provider.add_span_processor(self._processor)

        # Register enricher for on_end modifications
        register_span_enricher(enrich_agent_framework_span)

    def _uninstrument(self, **kwargs: Any) -> None:
        """
        Remove Agent Framework instrumentation.
        """
        # Unregister the enricher
        unregister_span_enricher()

        # Shutdown the processor
        if hasattr(self, "_processor"):
            self._processor.shutdown()

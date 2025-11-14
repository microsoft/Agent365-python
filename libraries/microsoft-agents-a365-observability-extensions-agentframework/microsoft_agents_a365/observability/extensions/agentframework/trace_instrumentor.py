# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from microsoft_agents_a365.observability.core.config import get_tracer_provider, is_configured
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

from microsoft_agents_a365.observability.extensions.agentframework.span_processor import (
    AgentFrameworkSpanProcessor,
)

# -----------------------------
# 3) The Instrumentor class
# -----------------------------
_instruments = ("agent-framework-azure-ai >= 0.1.0",)


class AgentFrameworkInstrumentor(BaseInstrumentor):
    """
    Instruments Agent Framework:
      • Installs your custom OTel SpanProcessor
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
        self._processor = AgentFrameworkSpanProcessor()
        provider.add_span_processor(self._processor)

    def _uninstrument(self, **kwargs: Any) -> None:
        pass

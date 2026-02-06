# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Wrapper for OpenAI Agents SDK

import logging
from collections.abc import Collection
from typing import Any, cast

import opentelemetry.trace as optel_trace
from agents import set_trace_processors
from microsoft_agents_a365.observability.core import get_tracer, get_tracer_provider, is_configured
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import Tracer

from .trace_processor import OpenAIAgentsTraceProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_instruments = ("openai-agents >= 0.2.6",)


class OpenAIAgentsTraceInstrumentor(BaseInstrumentor):
    """
    Custom Trace Processor for OpenAI Agents SDK using Microsoft Agent 365.
    Forwards OpenAI Agents SDK traces and spans to Microsoft Agent 365's tracing scopes.

    ```
    """

    def __init__(self):
        """Initialize the OpenAIAgentsTraceInstrumentor.
        Raises: RuntimeError: If Microsoft Agent 365 is not configured.
        """
        # Verify if Microsoft Agent 365 is configured
        Agent365_status = is_configured()
        if not Agent365_status:
            raise RuntimeError(
                "Microsoft Agent 365 is not configured yet. Please configure Microsoft Agent 365 before initializing this instrumentor."
            )
        super().__init__()

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """Instruments the OpenAI Agents SDK with Microsoft Agent 365 tracing."""
        tracer_name = kwargs["tracer_name"] if kwargs.get("tracer_name") else None
        tracer_version = kwargs["tracer_version"] if kwargs.get("tracer_version") else None

        # Get the configured Microsoft Agent 365 Tracer
        try:
            tracer = get_tracer(tracer_name, tracer_version)
        except Exception:
            # fallback
            tracer = optel_trace.get_tracer(tracer_name, tracer_version)

        # Get the configured Microsoft Agent 365 Tracer Provider instance
        try:
            get_tracer_provider()
        except Exception:
            # fallback
            optel_trace.get_tracer_provider()

        agent365_tracer = cast(Tracer, tracer)

        set_trace_processors([OpenAIAgentsTraceProcessor(agent365_tracer)])

    def _uninstrument(self, **kwargs: Any) -> None:
        pass

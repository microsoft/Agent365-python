# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Microsoft Agent 365 Python SDK for OpenTelemetry tracing.

from .agent_details import AgentDetails
from .config import (
    configure,
    get_tracer,
    get_tracer_provider,
    is_configured,
)
from .execute_tool_scope import ExecuteToolScope
from .exporters.agent365_exporter_options import Agent365ExporterOptions
from .exporters.enriched_span import EnrichedReadableSpan
from .exporters.enriching_span_processor import (
    get_span_enricher,
    register_span_enricher,
    unregister_span_enricher,
)
from .exporters.spectra_exporter_options import SpectraExporterOptions
from .inference_call_details import InferenceCallDetails, ServiceEndpoint
from .inference_operation_type import InferenceOperationType
from .inference_scope import InferenceScope
from .invoke_agent_details import InvokeAgentScopeDetails
from .invoke_agent_scope import InvokeAgentScope
from .middleware.baggage_builder import BaggageBuilder
from .models.caller_details import CallerDetails
from .models.user_details import UserDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .channel import Channel
from .span_details import SpanDetails
from .spans_scopes.output_scope import OutputScope
from .tool_call_details import ToolCallDetails
from .tool_type import ToolType
from .trace_processor.span_processor import SpanProcessor
from .utils import extract_context_from_headers, get_traceparent

__all__ = [
    # Main SDK functions
    "configure",
    "is_configured",
    "get_tracer",
    "get_tracer_provider",
    # Exporter options
    "Agent365ExporterOptions",
    "SpectraExporterOptions",
    # Span enrichment
    "register_span_enricher",
    "unregister_span_enricher",
    "get_span_enricher",
    "EnrichedReadableSpan",
    # Span processor
    "SpanProcessor",
    # Base scope class
    "OpenTelemetryScope",
    # Specific scope classes
    "ExecuteToolScope",
    "InvokeAgentScope",
    "InferenceScope",
    "OutputScope",
    # Middleware
    "BaggageBuilder",
    # Data classes
    "InvokeAgentScopeDetails",
    "AgentDetails",
    "CallerDetails",
    "UserDetails",
    "ToolCallDetails",
    "Channel",
    "Request",
    "SpanDetails",
    "InferenceCallDetails",
    "ServiceEndpoint",
    # Enums
    "InferenceOperationType",
    "ToolType",
    # Utility functions
    "extract_context_from_headers",
    "get_traceparent",
]

# This is a namespace package
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

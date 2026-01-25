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
from .execution_type import ExecutionType
from .inference_call_details import InferenceCallDetails
from .inference_operation_type import InferenceOperationType
from .inference_scope import InferenceScope
from .invoke_agent_details import InvokeAgentDetails
from .invoke_agent_scope import InvokeAgentScope
from .middleware.baggage_builder import BaggageBuilder
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .source_metadata import SourceMetadata
from .tenant_details import TenantDetails
from .tool_call_details import ToolCallDetails
from .tool_type import ToolType
from .trace_processor.span_processor import SpanProcessor

__all__ = [
    # Main SDK functions
    "configure",
    "is_configured",
    "get_tracer",
    "get_tracer_provider",
    # Span processor
    "SpanProcessor",
    # Base scope class
    "OpenTelemetryScope",
    # Specific scope classes
    "ExecuteToolScope",
    "InvokeAgentScope",
    "InferenceScope",
    # Middleware
    "BaggageBuilder",
    # Data classes
    "InvokeAgentDetails",
    "AgentDetails",
    "TenantDetails",
    "ToolCallDetails",
    "SourceMetadata",
    "Request",
    "InferenceCallDetails",
    # Enums
    "ExecutionType",
    "InferenceOperationType",
    "ToolType",
    # Constants
    # all constants from constants.py are exported via *
]

# This is a namespace package
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

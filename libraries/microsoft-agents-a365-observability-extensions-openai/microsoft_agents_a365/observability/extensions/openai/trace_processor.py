# Copyright (c) Microsoft. All rights reserved.

# Processor for OpenAI Agents SDK

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, assert_never

from agents import MCPListToolsSpanData
from agents.tracing import Span, Trace, TracingProcessor
from agents.tracing.span_data import (
    AgentSpanData,
    FunctionSpanData,
    GenerationSpanData,
    HandoffSpanData,
    ResponseSpanData,
)
from microsoft_agents_a365.observability.core.constants import (
    CUSTOM_PARENT_SPAN_ID_KEY,
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_SYSTEM_KEY,
    GEN_AI_TOOL_CALL_ID_KEY,
    GEN_AI_TOOL_TYPE_KEY,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.execution_type import ExecutionType
from microsoft_agents_a365.observability.core.utils import as_utc_nano, safe_json_dumps
from opentelemetry import trace as ot_trace
from opentelemetry.context import attach, detach
from opentelemetry.trace import Span as OtelSpan
from opentelemetry.trace import (
    Status,
    StatusCode,
    Tracer,
    set_span_in_context,
)

from openai.types.responses import (
    Response,
)

from .constants import (
    GEN_AI_GRAPH_NODE_PARENT_ID,
)
from .utils import (
    capture_input_message,
    capture_output_message,
    capture_tool_call_ids,
    find_ancestor_agent_span_id,
    get_attributes_from_function_span_data,
    get_attributes_from_generation_span_data,
    get_attributes_from_input,
    get_attributes_from_mcp_list_tool_span_data,
    get_attributes_from_response,
    get_span_kind,
    get_span_name,
    get_span_status,
    get_tool_call_id,
)

logger = logging.getLogger(__name__)


"""
Custom Trace Processor for OpenAI Agents SDK
"""


class OpenAIAgentsTraceProcessor(TracingProcessor):
    _MAX_HANDOFFS_IN_FLIGHT = 1000
    _MAX_PENDING_TOOL_CALLS = 1000

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer
        self._root_spans: dict[str, OtelSpan] = {}
        self._otel_spans: dict[str, OtelSpan] = {}
        self._tokens: dict[str, object] = {}
        # This captures in flight handoff. Once the handoff is complete, the entry is deleted
        # If the handoff does not complete, the entry stays in the dict.
        # Use an OrderedDict and _MAX_HANDOFFS_IN_FLIGHT to cap the size of the dict
        # in case there are large numbers of orphaned handoffs
        self._reverse_handoffs_dict: OrderedDict[str, str] = OrderedDict()
        # Track input/output messages for agent spans (keyed by agent span_id)
        self._agent_inputs: dict[str, str] = {}
        self._agent_outputs: dict[str, str] = {}
        # Track agent span IDs to find nearest ancestor
        self._agent_span_ids: set[str] = set()
        # Track parent-child relationships: child_span_id -> parent_span_id
        self._span_parents: dict[str, str] = {}
        # Track tool_call_ids from GenerationSpan: (function_name, trace_id) -> call_id
        # Use an OrderedDict and _MAX_PENDING_TOOL_CALLS to cap the size of the dict
        # in case tool calls are captured but never consumed
        self._pending_tool_calls: OrderedDict[str, str] = OrderedDict()

    # helper
    def _stamp_custom_parent(self, otel_span: OtelSpan, trace_id: str) -> None:
        root = self._root_spans.get(trace_id)
        if not root:
            return
        sc = root.get_span_context()
        pid_hex = "0x" + ot_trace.format_span_id(sc.span_id)
        otel_span.set_attribute(CUSTOM_PARENT_SPAN_ID_KEY, pid_hex)

    def on_trace_start(self, trace: Trace) -> None:
        """Called when a trace is started.

        Args:
            trace: The trace that started.
        """

    def on_trace_end(self, trace: Trace) -> None:
        """Called when a trace is finished.

        Args:
            trace: The trace that started.
        """
        if root_span := self._root_spans.pop(trace.trace_id, None):
            root_span.set_status(Status(StatusCode.OK))
            root_span.end()

    def on_span_start(self, span: Span[Any]) -> None:
        """Called when a span is started.

        Args:
            span: The span that started.
        """
        if not span.started_at:
            return
        start_time = datetime.fromisoformat(span.started_at)
        parent_span = (
            self._otel_spans.get(span.parent_id)
            if span.parent_id
            else self._root_spans.get(span.trace_id)
        )
        context = set_span_in_context(parent_span) if parent_span else None
        span_name = get_span_name(span)
        otel_span = self._tracer.start_span(
            name=span_name,
            context=context,
            start_time=as_utc_nano(start_time),
            attributes={
                GEN_AI_OPERATION_NAME_KEY: get_span_kind(span.span_data),
                GEN_AI_SYSTEM_KEY: "openai",
            },
        )
        self._otel_spans[span.span_id] = otel_span
        self._tokens[span.span_id] = attach(set_span_in_context(otel_span))
        # Track parent-child relationship for ancestor lookup
        if span.parent_id:
            self._span_parents[span.span_id] = span.parent_id
        # Track AgentSpan IDs
        if isinstance(span.span_data, AgentSpanData):
            self._agent_span_ids.add(span.span_id)

    def on_span_end(self, span: Span[Any]) -> None:
        """Called when a span is finished. Should not block or raise exceptions.

        Args:
            span: The span that finished.
        """
        if token := self._tokens.pop(span.span_id, None):
            detach(token)  # type: ignore[arg-type]
        # Clean up parent tracking
        self._span_parents.pop(span.span_id, None)
        if not (otel_span := self._otel_spans.pop(span.span_id, None)):
            return
        otel_span.update_name(get_span_name(span))

        data = span.span_data

        # DATA TYPES AS PER OPENAI AGENTS SDK
        if isinstance(data, ResponseSpanData):
            if hasattr(data, "response") and isinstance(response := data.response, Response):
                otel_span.set_attribute(GEN_AI_OUTPUT_MESSAGES_KEY, response.model_dump_json())
                for k, v in get_attributes_from_response(response):
                    otel_span.set_attribute(k, v)
            if hasattr(data, "input") and (input := data.input):
                if isinstance(input, str):
                    otel_span.set_attribute(GEN_AI_INPUT_MESSAGES_KEY, input)
                elif isinstance(input, list):
                    otel_span.set_attribute(GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps(input))
                    for k, v in get_attributes_from_input(input):
                        otel_span.set_attribute(k, v)
                elif TYPE_CHECKING:
                    assert_never(input)
        elif isinstance(data, GenerationSpanData):
            for k, v in get_attributes_from_generation_span_data(data):
                otel_span.set_attribute(k, v)
            self._stamp_custom_parent(otel_span, span.trace_id)
            # Capture input/output messages for nearest ancestor agent span
            if agent_span_id := find_ancestor_agent_span_id(
                span.parent_id, self._agent_span_ids, self._span_parents
            ):
                if data.input:
                    capture_input_message(agent_span_id, data.input, self._agent_inputs)
                if data.output:
                    capture_output_message(agent_span_id, data.output, self._agent_outputs)
            # Capture tool_call_ids for later use by FunctionSpan
            if data.output:
                capture_tool_call_ids(
                    data.output, self._pending_tool_calls, self._MAX_PENDING_TOOL_CALLS
                )
            otel_span.update_name(
                f"{otel_span.attributes[GEN_AI_OPERATION_NAME_KEY]} {otel_span.attributes[GEN_AI_REQUEST_MODEL_KEY]}"
            )
        elif isinstance(data, FunctionSpanData):
            for k, v in get_attributes_from_function_span_data(data):
                otel_span.set_attribute(k, v)
            self._stamp_custom_parent(otel_span, span.trace_id)
            otel_span.set_attribute(GEN_AI_TOOL_TYPE_KEY, data.type)
            # Set tool_call_id if available from preceding GenerationSpan
            func_args = data.input if data.input else ""
            if tool_call_id := get_tool_call_id(data.name, func_args, self._pending_tool_calls):
                otel_span.set_attribute(GEN_AI_TOOL_CALL_ID_KEY, tool_call_id)
            otel_span.update_name(f"{EXECUTE_TOOL_OPERATION_NAME} {data.name}")
        elif isinstance(data, MCPListToolsSpanData):
            for k, v in get_attributes_from_mcp_list_tool_span_data(data):
                otel_span.set_attribute(k, v)
        elif isinstance(data, HandoffSpanData):
            # Set this dict to find the parent node when the agent span starts
            if data.to_agent and data.from_agent:
                key = f"{data.to_agent}:{span.trace_id}"
                self._reverse_handoffs_dict[key] = data.from_agent
                # Cap the size of the dict
                while len(self._reverse_handoffs_dict) > self._MAX_HANDOFFS_IN_FLIGHT:
                    self._reverse_handoffs_dict.popitem(last=False)
        elif isinstance(data, AgentSpanData):
            otel_span.set_attribute(GEN_AI_EXECUTION_TYPE_KEY, ExecutionType.HUMAN_TO_AGENT.value)
            # Lookup the parent node if exists
            key = f"{data.name}:{span.trace_id}"
            if parent_node := self._reverse_handoffs_dict.pop(key, None):
                otel_span.set_attribute(GEN_AI_GRAPH_NODE_PARENT_ID, parent_node)
            # Apply captured input/output messages from child spans
            if input_msg := self._agent_inputs.pop(span.span_id, None):
                otel_span.set_attribute(GEN_AI_INPUT_MESSAGES_KEY, input_msg)
            if output_msg := self._agent_outputs.pop(span.span_id, None):
                otel_span.set_attribute(GEN_AI_OUTPUT_MESSAGES_KEY, output_msg)
            otel_span.update_name(f"{INVOKE_AGENT_OPERATION_NAME} {get_span_name(span)}")
            # Clean up tracking
            self._agent_span_ids.discard(span.span_id)

        end_time: int | None = None
        if span.ended_at:
            try:
                end_time = as_utc_nano(datetime.fromisoformat(span.ended_at))
            except ValueError:
                pass
        otel_span.set_status(status=get_span_status(span))
        otel_span.end(end_time)

    def force_flush(self) -> None:
        """Forces an immediate flush of all queued spans/traces."""
        pass

    def shutdown(self) -> None:
        """Called when the application stops."""
        pass

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from microsoft_agents_a365.observability.core.constants import (
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.exporters.enriched_span import EnrichedReadableSpan
from opentelemetry.sdk.trace import ReadableSpan

from .utils import extract_input_content, extract_output_content

# Agent Framework specific attribute keys
AF_TOOL_CALL_ARGUMENTS_KEY = "gen_ai.tool.call.arguments"
AF_TOOL_CALL_RESULT_KEY = "gen_ai.tool.call.result"


def enrich_agent_framework_span(span: ReadableSpan) -> ReadableSpan:
    """
    Enricher function for Agent Framework spans.
    """
    extra_attributes = {}
    attributes = span.attributes or {}

    # Only extract content for invoke_agent spans
    if span.name.startswith(INVOKE_AGENT_OPERATION_NAME):
        # Extract all text content from input messages
        input_messages = attributes.get(GEN_AI_INPUT_MESSAGES_KEY)
        if input_messages:
            extra_attributes[GEN_AI_INPUT_MESSAGES_KEY] = extract_input_content(input_messages)

        output_messages = attributes.get(GEN_AI_OUTPUT_MESSAGES_KEY)
        if output_messages:
            extra_attributes[GEN_AI_OUTPUT_MESSAGES_KEY] = extract_output_content(output_messages)

    # Map tool attributes for execute_tool spans
    elif span.name.startswith(EXECUTE_TOOL_OPERATION_NAME):
        if AF_TOOL_CALL_ARGUMENTS_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_ARGS_KEY] = attributes[AF_TOOL_CALL_ARGUMENTS_KEY]

        if AF_TOOL_CALL_RESULT_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_CALL_RESULT_KEY] = attributes[AF_TOOL_CALL_RESULT_KEY]

    if extra_attributes:
        return EnrichedReadableSpan(span, extra_attributes)

    return span

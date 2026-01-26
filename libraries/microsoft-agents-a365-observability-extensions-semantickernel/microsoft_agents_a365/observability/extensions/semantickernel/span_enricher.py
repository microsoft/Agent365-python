# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Span enricher for Semantic Kernel."""

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

from .utils import extract_content_as_string_list

# Semantic Kernel specific attribute keys
SK_TOOL_CALL_ARGUMENTS_KEY = "gen_ai.tool.call.arguments"
SK_TOOL_CALL_RESULT_KEY = "gen_ai.tool.call.result"


def enrich_semantic_kernel_span(span: ReadableSpan) -> ReadableSpan:
    """
    Enricher function for Semantic Kernel spans.

    Transforms SK-specific attributes to standard gen_ai attributes
    before the span is exported. Enrichment is applied based on span type:
    - invoke_agent spans: Extract only content from input/output messages
    - execute_tool spans: Map tool arguments and results to standard keys

    Args:
        span: The ReadableSpan to enrich.

    Returns:
        The enriched span (wrapped if attributes were added), or the
        original span if no enrichment was needed.
    """
    extra_attributes = {}
    attributes = span.attributes or {}

    # Only extract content for invoke_agent spans
    if span.name.startswith(INVOKE_AGENT_OPERATION_NAME):
        # Transform SK-specific agent invocation attributes to standard gen_ai attributes
        # Extract only the content from the full message objects
        # Support both gen_ai.agent.invocation_input and gen_ai.input_messages as sources
        input_messages = attributes.get("gen_ai.agent.invocation_input") or attributes.get(
            GEN_AI_INPUT_MESSAGES_KEY
        )
        if input_messages:
            extra_attributes[GEN_AI_INPUT_MESSAGES_KEY] = extract_content_as_string_list(
                input_messages
            )

        output_messages = attributes.get("gen_ai.agent.invocation_output") or attributes.get(
            GEN_AI_OUTPUT_MESSAGES_KEY
        )
        if output_messages:
            extra_attributes[GEN_AI_OUTPUT_MESSAGES_KEY] = extract_content_as_string_list(
                output_messages
            )

    # Map tool attributes for execute_tool spans
    elif span.name.startswith(EXECUTE_TOOL_OPERATION_NAME):
        if SK_TOOL_CALL_ARGUMENTS_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_ARGS_KEY] = attributes[SK_TOOL_CALL_ARGUMENTS_KEY]

        if SK_TOOL_CALL_RESULT_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_CALL_RESULT_KEY] = attributes[SK_TOOL_CALL_RESULT_KEY]

    if extra_attributes:
        return EnrichedReadableSpan(span, extra_attributes)

    return span

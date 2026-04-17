# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from microsoft_agents_a365.observability.core.constants import (
    CHAT_OPERATION_NAME,
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.exporters.enriched_span import EnrichedReadableSpan
from opentelemetry.sdk.trace import ReadableSpan

from .message_mapper import map_input_messages, map_output_messages

# Agent Framework specific attribute keys
AF_TOOL_CALL_ARGUMENTS_KEY = "gen_ai.tool.call.arguments"
AF_TOOL_CALL_RESULT_KEY = "gen_ai.tool.call.result"

_MESSAGE_OPERATIONS = {INVOKE_AGENT_OPERATION_NAME, CHAT_OPERATION_NAME}


def enrich_agent_framework_span(span: ReadableSpan) -> ReadableSpan:
    """Enricher function for Agent Framework spans.

    For ``invoke_agent`` and ``chat`` operations, maps the raw
    ``gen_ai.input.messages`` / ``gen_ai.output.messages`` JSON arrays
    to the A365 versioned format.

    For ``execute_tool`` operations, maps Agent Framework tool attribute
    keys to the A365 standard keys.
    """
    extra_attributes: dict[str, str] = {}
    attributes = span.attributes or {}
    operation = attributes.get(GEN_AI_OPERATION_NAME_KEY, "")

    is_message_span = operation in _MESSAGE_OPERATIONS or span.name.startswith(
        INVOKE_AGENT_OPERATION_NAME
    )
    is_tool_span = operation == EXECUTE_TOOL_OPERATION_NAME or span.name.startswith(
        EXECUTE_TOOL_OPERATION_NAME
    )

    if is_message_span:
        input_messages = attributes.get(GEN_AI_INPUT_MESSAGES_KEY)
        if input_messages:
            mapped = map_input_messages(input_messages)
            if mapped is not None:
                extra_attributes[GEN_AI_INPUT_MESSAGES_KEY] = mapped

        output_messages = attributes.get(GEN_AI_OUTPUT_MESSAGES_KEY)
        if output_messages:
            mapped = map_output_messages(output_messages)
            if mapped is not None:
                extra_attributes[GEN_AI_OUTPUT_MESSAGES_KEY] = mapped

    elif is_tool_span:
        if AF_TOOL_CALL_ARGUMENTS_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_ARGS_KEY] = attributes[AF_TOOL_CALL_ARGUMENTS_KEY]

        if AF_TOOL_CALL_RESULT_KEY in attributes:
            extra_attributes[GEN_AI_TOOL_CALL_RESULT_KEY] = attributes[AF_TOOL_CALL_RESULT_KEY]

    if extra_attributes:
        return EnrichedReadableSpan(span, extra_attributes)

    return span

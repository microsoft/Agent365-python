# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Custom Span Processor

from opentelemetry.sdk.trace.export import SpanProcessor

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_OPERATION_NAME_KEY,
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_EVENT_CONTENT,
)


class AgentFrameworkSpanProcessor(SpanProcessor):
    """
    SpanProcessor for Agent Framework.
    """

    TOOL_CALL_RESULT_TAG = "gen_ai.tool.call.result"

    def __init__(self, service_name: str | None = None):
        self.service_name = service_name
        super().__init__()

    def on_start(self, span, parent_context):
        if hasattr(span, "attributes"):
            operation_name = span.attributes.get(GEN_AI_OPERATION_NAME_KEY)
            if isinstance(operation_name, str) and operation_name == EXECUTE_TOOL_OPERATION_NAME:
                tool_call_result = span.attributes.get(self.TOOL_CALL_RESULT_TAG)
                if tool_call_result is not None:
                    span.set_attribute(GEN_AI_EVENT_CONTENT, tool_call_result)

    def on_end(self, span):
        pass

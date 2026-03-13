# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from opentelemetry.sdk.trace.export import SpanProcessor


class AgentFrameworkSpanProcessor(SpanProcessor):
    """SpanProcessor for Agent Framework.

    Note: The span processing logic was removed as GEN_AI_EVENT_CONTENT is no longer used.
    This processor is kept for interface compatibility.
    """

    TOOL_CALL_RESULT_TAG = "gen_ai.tool.call.result"

    def __init__(self, service_name: str | None = None):
        self.service_name = service_name
        super().__init__()

    def on_start(self, span, parent_context):
        """Called when a span starts. Intentionally a no-op."""
        pass

    def on_end(self, span):
        """Called when a span ends. Intentionally a no-op."""
        pass

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.execution_type import ExecutionType
from microsoft_agents_a365.observability.core.inference_operation_type import InferenceOperationType
from microsoft_agents_a365.observability.core.utils import extract_model_name
from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import SpanProcessor


class SemanticKernelSpanProcessor(SpanProcessor):
    """
    SpanProcessor for SK
    """

    def __init__(self, service_name: str | None = None):
        """
        Initialize the Semantic Kernel span processor.

        Args:
            service_name: Optional service name for span enrichment.
        """
        self.service_name = service_name

    def on_start(self, span: Span, parent_context: context_api.Context | None) -> None:
        """
        Modify span while it's still writable.

        Args:
            span: The span that is starting (writable).
            parent_context: The parent context of the span.
        """
        if span.name.startswith("chat."):
            span.set_attribute(GEN_AI_OPERATION_NAME_KEY, InferenceOperationType.CHAT.value.lower())
            model_name = extract_model_name(span.name)
            span.update_name(f"{InferenceOperationType.CHAT.value.lower()} {model_name}")

        if span.name.startswith(INVOKE_AGENT_OPERATION_NAME):
            span.set_attribute(
                GEN_AI_EXECUTION_TYPE_KEY, ExecutionType.HUMAN_TO_AGENT.value.lower()
            )

    def on_end(self, span: ReadableSpan) -> None:
        """
        Called when a span ends.
        """
        pass

    def shutdown(self) -> None:
        """Shutdown the processor."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending spans."""
        return True

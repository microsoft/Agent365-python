# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Custom Span Processor

from microsoft_agents_a365.observability.core.constants import GEN_AI_OPERATION_NAME_KEY
from microsoft_agents_a365.observability.core.inference_operation_type import InferenceOperationType
from microsoft_agents_a365.observability.core.utils import extract_model_name
from opentelemetry.sdk.trace.export import SpanProcessor


class SemanticKernelSpanProcessor(SpanProcessor):
    """
    SpanProcessor for SK
    """

    def __init__(self, service_name: str | None = None):
        self.service_name = service_name

    def on_start(self, span, parent_context):
        if span.name.startswith("chat."):
            span.set_attribute(GEN_AI_OPERATION_NAME_KEY, InferenceOperationType.CHAT.value.lower())
            model_name = extract_model_name(span.name)
            span.update_name(f"{InferenceOperationType.CHAT.value.lower()} {model_name}")

    def on_end(self, span):
        pass

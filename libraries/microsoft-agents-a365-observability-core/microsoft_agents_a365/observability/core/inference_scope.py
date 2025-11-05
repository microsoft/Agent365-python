# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import List

from .agent_details import AgentDetails
from .constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_PROVIDER_NAME_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_RESPONSE_FINISH_REASONS_KEY,
    GEN_AI_RESPONSE_ID_KEY,
    GEN_AI_THOUGHT_PROCESS_KEY,
    GEN_AI_USAGE_INPUT_TOKENS_KEY,
    GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
)
from .inference_call_details import InferenceCallDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .tenant_details import TenantDetails
from .utils import safe_json_dumps


class InferenceScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for generative AI inference operations."""

    @staticmethod
    def start(
        details: InferenceCallDetails,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
    ) -> "InferenceScope":
        """Creates and starts a new scope for inference tracing.

        Args:
            details: The details of the inference call
            agent_details: The details of the agent making the call
            tenant_details: The details of the tenant
            request: Optional request details for additional context

        Returns:
            A new InferenceScope instance
        """
        return InferenceScope(details, agent_details, tenant_details, request)

    def __init__(
        self,
        details: InferenceCallDetails,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
    ):
        """Initialize the inference scope.

        Args:
            details: The details of the inference call
            agent_details: The details of the agent making the call
            tenant_details: The details of the tenant
            request: Optional request details for additional context
        """

        super().__init__(
            kind="Client",
            operation_name=details.operationName.value,
            activity_name=f"{details.operationName.value} {details.model}",
            agent_details=agent_details,
            tenant_details=tenant_details,
        )

        if request:
            self.set_tag_maybe(GEN_AI_INPUT_MESSAGES_KEY, request.content)

        self.set_tag_maybe(GEN_AI_OPERATION_NAME_KEY, details.operationName.value)
        self.set_tag_maybe(GEN_AI_REQUEST_MODEL_KEY, details.model)
        self.set_tag_maybe(GEN_AI_PROVIDER_NAME_KEY, details.providerName)
        self.set_tag_maybe(
            GEN_AI_USAGE_INPUT_TOKENS_KEY,
            str(details.inputTokens) if details.inputTokens is not None else None,
        )
        self.set_tag_maybe(
            GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
            str(details.outputTokens) if details.outputTokens is not None else None,
        )
        self.set_tag_maybe(
            GEN_AI_RESPONSE_FINISH_REASONS_KEY,
            safe_json_dumps(details.finishReasons) if details.finishReasons else None,
        )
        self.set_tag_maybe(GEN_AI_RESPONSE_ID_KEY, details.responseId)

    def record_input_messages(self, messages: List[str]) -> None:
        """Records the input messages for telemetry tracking.

        Args:
            messages: List of input messages
        """
        self.set_tag_maybe(GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps(messages))

    def record_output_messages(self, messages: List[str]) -> None:
        """Records the output messages for telemetry tracking.

        Args:
            messages: List of output messages
        """
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(messages))

    def record_input_tokens(self, input_tokens: int) -> None:
        """Records the number of input tokens for telemetry tracking.

        Args:
            input_tokens: Number of input tokens
        """
        self.set_tag_maybe(GEN_AI_USAGE_INPUT_TOKENS_KEY, str(input_tokens))

    def record_output_tokens(self, output_tokens: int) -> None:
        """Records the number of output tokens for telemetry tracking.

        Args:
            output_tokens: Number of output tokens
        """
        self.set_tag_maybe(GEN_AI_USAGE_OUTPUT_TOKENS_KEY, str(output_tokens))

    def record_finish_reasons(self, finish_reasons: List[str]) -> None:
        """Records the finish reasons for telemetry tracking.

        Args:
            finish_reasons: List of finish reasons
        """
        if finish_reasons:
            self.set_tag_maybe(GEN_AI_RESPONSE_FINISH_REASONS_KEY, safe_json_dumps(finish_reasons))

    def record_thought_process(self, thought_process: str) -> None:
        """Records the thought process.

        Args:
            thought_process: The thought process to record
        """
        self.set_tag_maybe(GEN_AI_THOUGHT_PROCESS_KEY, thought_process)

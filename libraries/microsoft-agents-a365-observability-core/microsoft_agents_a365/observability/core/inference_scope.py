# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import List

from opentelemetry.trace import SpanKind

from .agent_details import AgentDetails
from .constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_AGENT_THOUGHT_PROCESS_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_PROVIDER_NAME_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_RESPONSE_FINISH_REASONS_KEY,
    GEN_AI_USAGE_INPUT_TOKENS_KEY,
    GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
    GEN_AI_CALLER_CLIENT_IP_KEY,
)
from .inference_call_details import InferenceCallDetails
from .models.user_details import UserDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .span_details import SpanDetails
from .utils import safe_json_dumps, validate_and_normalize_ip


class InferenceScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for generative AI inference operations."""

    @staticmethod
    def start(
        request: Request,
        details: InferenceCallDetails,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ) -> "InferenceScope":
        """Creates and starts a new scope for inference tracing.

        Args:
            request: Request details for the inference
            details: The details of the inference call
            agent_details: The details of the agent making the call
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing)

        Returns:
            A new InferenceScope instance
        """
        return InferenceScope(request, details, agent_details, user_details, span_details)

    def __init__(
        self,
        request: Request,
        details: InferenceCallDetails,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ):
        """Initialize the inference scope.

        Args:
            request: Request details for the inference
            details: The details of the inference call
            agent_details: The details of the agent making the call
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing)
        """
        # spanKind for InferenceScope is always CLIENT
        resolved_span_details = (
            SpanDetails(
                span_kind=SpanKind.CLIENT,
                parent_context=span_details.parent_context if span_details else None,
                start_time=span_details.start_time if span_details else None,
                end_time=span_details.end_time if span_details else None,
                span_links=span_details.span_links if span_details else None,
            )
            if span_details
            else SpanDetails(span_kind=SpanKind.CLIENT)
        )

        super().__init__(
            operation_name=details.operationName.value,
            activity_name=f"{details.operationName.value} {details.model}",
            agent_details=agent_details,
            span_details=resolved_span_details,
        )

        if request.content:
            self.set_tag_maybe(GEN_AI_INPUT_MESSAGES_KEY, request.content)
        self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)

        self.set_tag_maybe(GEN_AI_OPERATION_NAME_KEY, details.operationName.value)
        self.set_tag_maybe(GEN_AI_REQUEST_MODEL_KEY, details.model)
        self.set_tag_maybe(GEN_AI_PROVIDER_NAME_KEY, details.providerName)
        self.set_tag_maybe(
            GEN_AI_USAGE_INPUT_TOKENS_KEY,
            details.inputTokens if details.inputTokens is not None else None,
        )
        self.set_tag_maybe(
            GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
            details.outputTokens if details.outputTokens is not None else None,
        )
        self.set_tag_maybe(
            GEN_AI_RESPONSE_FINISH_REASONS_KEY,
            safe_json_dumps(details.finishReasons) if details.finishReasons else None,
        )
        self.set_tag_maybe(GEN_AI_AGENT_THOUGHT_PROCESS_KEY, details.thoughtProcess)

        # Set endpoint information if provided
        if details.endpoint:
            self.set_tag_maybe(SERVER_ADDRESS_KEY, details.endpoint.hostname)
            if details.endpoint.port:
                self.set_tag_maybe(SERVER_PORT_KEY, str(details.endpoint.port))

        # Set request metadata if provided
        if request.channel:
            self.set_tag_maybe(CHANNEL_NAME_KEY, request.channel.name)
            self.set_tag_maybe(CHANNEL_LINK_KEY, request.channel.link)

        # Set user details if provided
        if user_details:
            self.set_tag_maybe(USER_ID_KEY, user_details.user_id)
            self.set_tag_maybe(USER_EMAIL_KEY, user_details.user_email)
            self.set_tag_maybe(USER_NAME_KEY, user_details.user_name)
            self.set_tag_maybe(
                GEN_AI_CALLER_CLIENT_IP_KEY,
                validate_and_normalize_ip(user_details.user_client_ip),
            )

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
        self.set_tag_maybe(GEN_AI_USAGE_INPUT_TOKENS_KEY, input_tokens)

    def record_output_tokens(self, output_tokens: int) -> None:
        """Records the number of output tokens for telemetry tracking.

        Args:
            output_tokens: Number of output tokens
        """
        self.set_tag_maybe(GEN_AI_USAGE_OUTPUT_TOKENS_KEY, output_tokens)

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
        self.set_tag_maybe(GEN_AI_AGENT_THOUGHT_PROCESS_KEY, thought_process)

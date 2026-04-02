# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Invoke agent scope for tracing agent invocation.

import logging

from opentelemetry.trace import SpanKind

from .agent_details import AgentDetails
from .constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY,
    GEN_AI_CALLER_AGENT_EMAIL_KEY,
    GEN_AI_CALLER_AGENT_ID_KEY,
    GEN_AI_CALLER_AGENT_NAME_KEY,
    GEN_AI_CALLER_AGENT_PLATFORM_ID_KEY,
    GEN_AI_CALLER_AGENT_USER_ID_KEY,
    GEN_AI_CALLER_AGENT_VERSION_KEY,
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    INVOKE_AGENT_OPERATION_NAME,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
    SESSION_ID_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from .invoke_agent_details import InvokeAgentScopeDetails
from .models.caller_details import CallerDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .span_details import SpanDetails
from .utils import safe_json_dumps, validate_and_normalize_ip

logger = logging.getLogger(__name__)


class InvokeAgentScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for AI agent invocation operations."""

    @staticmethod
    def start(
        request: Request,
        scope_details: InvokeAgentScopeDetails,
        agent_details: AgentDetails,
        caller_details: CallerDetails | None = None,
        span_details: SpanDetails | None = None,
    ) -> "InvokeAgentScope":
        """Create and start a new scope for agent invocation tracing.

        Args:
            request: Request details for the invocation
            scope_details: Scope-level configuration (endpoint)
            agent_details: The details of the agent being invoked
            caller_details: Optional composite caller details (human user and/or
                calling agent for A2A scenarios)
            span_details: Optional span configuration (parent context, timing, kind)

        Returns:
            A new InvokeAgentScope instance
        """
        return InvokeAgentScope(
            request,
            scope_details,
            agent_details,
            caller_details,
            span_details,
        )

    def __init__(
        self,
        request: Request,
        scope_details: InvokeAgentScopeDetails,
        agent_details: AgentDetails,
        caller_details: CallerDetails | None = None,
        span_details: SpanDetails | None = None,
    ):
        """Initialize the agent invocation scope.

        Args:
            request: Request details for the invocation
            scope_details: Scope-level configuration (endpoint)
            agent_details: The details of the agent being invoked
            caller_details: Optional composite caller details (human user and/or
                calling agent for A2A scenarios)
            span_details: Optional span configuration (parent context, timing, kind)
        """
        activity_name = INVOKE_AGENT_OPERATION_NAME
        if agent_details.agent_name:
            activity_name = f"{INVOKE_AGENT_OPERATION_NAME} {agent_details.agent_name}"

        # spanKind defaults to CLIENT; allow override via span_details
        resolved_span_details = (
            SpanDetails(
                span_kind=span_details.span_kind
                if span_details and span_details.span_kind
                else SpanKind.CLIENT,
                parent_context=span_details.parent_context if span_details else None,
                start_time=span_details.start_time if span_details else None,
                end_time=span_details.end_time if span_details else None,
                span_links=span_details.span_links if span_details else None,
            )
            if span_details
            else SpanDetails(span_kind=SpanKind.CLIENT)
        )

        super().__init__(
            operation_name=INVOKE_AGENT_OPERATION_NAME,
            activity_name=activity_name,
            agent_details=agent_details,
            span_details=resolved_span_details,
        )

        self.set_tag_maybe(SESSION_ID_KEY, request.session_id)
        self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)

        endpoint = scope_details.endpoint
        if endpoint:
            self.set_tag_maybe(SERVER_ADDRESS_KEY, endpoint.hostname)
            if endpoint.port and endpoint.port != 443:
                self.set_tag_maybe(SERVER_PORT_KEY, endpoint.port)

        # Set request metadata
        if request.channel:
            self.set_tag_maybe(CHANNEL_NAME_KEY, request.channel.name)
            self.set_tag_maybe(CHANNEL_LINK_KEY, request.channel.link)
        if request.content:
            self.set_tag_maybe(GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps([request.content]))

        # Set caller details tags
        if caller_details:
            user_details = caller_details.user_details
            if user_details:
                self.set_tag_maybe(USER_ID_KEY, user_details.user_id)
                self.set_tag_maybe(USER_EMAIL_KEY, user_details.user_email)
                self.set_tag_maybe(USER_NAME_KEY, user_details.user_name)
                self.set_tag_maybe(
                    GEN_AI_CALLER_CLIENT_IP_KEY,
                    validate_and_normalize_ip(user_details.user_client_ip),
                )

            # Set caller agent details tags
            caller_agent_details = caller_details.caller_agent_details
            if caller_agent_details:
                self.set_tag_maybe(GEN_AI_CALLER_AGENT_NAME_KEY, caller_agent_details.agent_name)
                self.set_tag_maybe(GEN_AI_CALLER_AGENT_ID_KEY, caller_agent_details.agent_id)
                self.set_tag_maybe(
                    GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY,
                    caller_agent_details.agent_blueprint_id,
                )
                self.set_tag_maybe(
                    GEN_AI_CALLER_AGENT_USER_ID_KEY, caller_agent_details.agentic_user_id
                )
                self.set_tag_maybe(
                    GEN_AI_CALLER_AGENT_EMAIL_KEY, caller_agent_details.agentic_user_email
                )
                self.set_tag_maybe(
                    GEN_AI_CALLER_AGENT_PLATFORM_ID_KEY,
                    caller_agent_details.agent_platform_id,
                )
                self.set_tag_maybe(
                    GEN_AI_CALLER_AGENT_VERSION_KEY,
                    caller_agent_details.agent_version,
                )

    def record_response(self, response: str) -> None:
        """Record response information for telemetry tracking.

        Args:
            response: The response string to record
        """
        self.record_output_messages([response])

    def record_input_messages(self, messages: list[str]) -> None:
        """Record the input messages for telemetry tracking.

        Args:
            messages: List of input messages to record
        """
        self.set_tag_maybe(GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps(messages))

    def record_output_messages(self, messages: list[str]) -> None:
        """Record the output messages for telemetry tracking.

        Args:
            messages: List of output messages to record
        """
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(messages))

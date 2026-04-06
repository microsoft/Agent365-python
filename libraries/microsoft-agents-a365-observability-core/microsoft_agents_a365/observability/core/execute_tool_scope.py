# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from opentelemetry.trace import SpanKind

from .agent_details import AgentDetails
from .constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_ID_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
    GEN_AI_TOOL_DESCRIPTION_KEY,
    GEN_AI_TOOL_NAME_KEY,
    GEN_AI_TOOL_TYPE_KEY,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from .utils import safe_json_dumps, validate_and_normalize_ip
from .models.user_details import UserDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .span_details import SpanDetails
from .tool_call_details import ToolCallDetails


class ExecuteToolScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for AI tool execution operations."""

    @staticmethod
    def start(
        request: Request,
        details: ToolCallDetails,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ) -> "ExecuteToolScope":
        """Creates and starts a new scope for tool execution tracing.

        Args:
            request: Request details for the tool execution
            details: The details of the tool call
            agent_details: The details of the agent making the call
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing, kind)

        Returns:
            A new ExecuteToolScope instance
        """
        return ExecuteToolScope(
            request,
            details,
            agent_details,
            user_details,
            span_details,
        )

    def __init__(
        self,
        request: Request,
        details: ToolCallDetails,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ):
        """Initialize the tool execution scope.

        Args:
            request: Request details for the tool execution
            details: The details of the tool call
            agent_details: The details of the agent making the call
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing, kind)
        """
        # spanKind defaults to INTERNAL; allow override via span_details
        resolved_span_details = (
            SpanDetails(
                span_kind=span_details.span_kind
                if span_details and span_details.span_kind
                else SpanKind.INTERNAL,
                parent_context=span_details.parent_context if span_details else None,
                start_time=span_details.start_time if span_details else None,
                end_time=span_details.end_time if span_details else None,
                span_links=span_details.span_links if span_details else None,
            )
            if span_details
            else SpanDetails(span_kind=SpanKind.INTERNAL)
        )

        super().__init__(
            operation_name=EXECUTE_TOOL_OPERATION_NAME,
            activity_name=f"{EXECUTE_TOOL_OPERATION_NAME} {details.tool_name}",
            agent_details=agent_details,
            span_details=resolved_span_details,
        )

        # Extract details
        tool_name = details.tool_name
        arguments = details.arguments
        tool_call_id = details.tool_call_id
        description = details.description
        tool_type = details.tool_type
        endpoint = details.endpoint

        self.set_tag_maybe(GEN_AI_TOOL_NAME_KEY, tool_name)
        if arguments is not None:
            serialized = safe_json_dumps(arguments) if isinstance(arguments, dict) else arguments
            self.set_tag_maybe(GEN_AI_TOOL_ARGS_KEY, serialized)
        self.set_tag_maybe(GEN_AI_TOOL_TYPE_KEY, tool_type)
        self.set_tag_maybe(GEN_AI_TOOL_CALL_ID_KEY, tool_call_id)
        self.set_tag_maybe(GEN_AI_TOOL_DESCRIPTION_KEY, description)
        self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)

        if endpoint:
            self.set_tag_maybe(SERVER_ADDRESS_KEY, endpoint.hostname)
            if endpoint.port and endpoint.port != 443:
                self.set_tag_maybe(SERVER_PORT_KEY, endpoint.port)

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

    def record_response(self, result: dict[str, object] | str) -> None:
        """Record the tool call result for telemetry tracking.

        Per OTEL spec, the result is expected to be an object. If a string
        is provided, it is recorded as-is (JSON string fallback). If a dict
        is provided, it is serialized to JSON.

        Args:
            result: Tool call result as a structured dict or JSON string
        """
        serialized = safe_json_dumps(result) if isinstance(result, dict) else result
        self.set_tag_maybe(GEN_AI_TOOL_CALL_RESULT_KEY, serialized)

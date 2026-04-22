# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from opentelemetry.trace import SpanKind

from ..agent_details import AgentDetails
from ..constants import (
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from ..message_utils import normalize_output_messages, serialize_messages
from ..models.messages import OutputMessages
from ..models.response import Response, ResponseMessagesParam
from ..models.user_details import UserDetails
from ..opentelemetry_scope import OpenTelemetryScope
from ..request import Request
from ..span_details import SpanDetails
from ..utils import safe_json_dumps, validate_and_normalize_ip

OUTPUT_OPERATION_NAME = "output_messages"


class OutputScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for output messages.

    Output messages are set once (via the constructor or ``record_output_messages``)
    rather than accumulated. For streaming scenarios, the agent developer should
    collect all output (e.g. via a list or string builder) and pass the final
    result to ``OutputScope``.
    """

    @staticmethod
    def start(
        request: Request,
        response: Response,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ) -> "OutputScope":
        """Creates and starts a new scope for output tracing.

        Args:
            request: Request details for the output
            response: The response details from the agent
            agent_details: The details of the agent
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing)

        Returns:
            A new OutputScope instance
        """
        return OutputScope(request, response, agent_details, user_details, span_details)

    def __init__(
        self,
        request: Request,
        response: Response,
        agent_details: AgentDetails,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ):
        """Initialize the output scope.

        Args:
            request: Request details for the output
            response: The response details from the agent
            agent_details: The details of the agent
            user_details: Optional human user details
            span_details: Optional span configuration (parent context, timing)
        """
        # spanKind for OutputScope is always CLIENT
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
            operation_name=OUTPUT_OPERATION_NAME,
            activity_name=(f"{OUTPUT_OPERATION_NAME} {agent_details.agent_id}"),
            agent_details=agent_details,
            span_details=resolved_span_details,
        )

        self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)
        self._set_output(response.messages)

        # Set user details if provided
        if user_details:
            self.set_tag_maybe(USER_ID_KEY, user_details.user_id)
            self.set_tag_maybe(USER_EMAIL_KEY, user_details.user_email)
            self.set_tag_maybe(USER_NAME_KEY, user_details.user_name)
            self.set_tag_maybe(
                GEN_AI_CALLER_CLIENT_IP_KEY,
                validate_and_normalize_ip(user_details.user_client_ip),
            )

    def _set_output(self, messages: ResponseMessagesParam) -> None:
        """Serialize and set the output messages attribute on the span."""
        if isinstance(messages, dict):
            self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(messages))
        else:
            normalized = normalize_output_messages(messages)
            wrapper = OutputMessages(messages=list(normalized.messages))
            self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, serialize_messages(wrapper))

    def record_output_messages(self, messages: ResponseMessagesParam) -> None:
        """Records the output messages for telemetry tracking.

        Overwrites any previously set output messages. Accepts a single string,
        a list of strings (auto-wrapped as OTEL OutputMessage), a versioned
        ``OutputMessages`` wrapper, or a ``dict[str, object]`` for tool call
        results (per OTEL spec).

        Args:
            messages: String(s), OutputMessages, or dict for tool call results
        """
        self._set_output(messages)

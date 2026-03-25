# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from ..agent_details import AgentDetails
from ..constants import (
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from ..models.response import Response
from ..models.user_details import UserDetails
from ..opentelemetry_scope import OpenTelemetryScope
from ..request import Request
from ..span_details import SpanDetails
from ..utils import safe_json_dumps, validate_and_normalize_ip

OUTPUT_OPERATION_NAME = "output_messages"


class OutputScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for output messages."""

    _MAX_OUTPUT_MESSAGES = 5000

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
        parent_context = None
        start_time = None
        end_time = None
        if span_details is not None:
            parent_context = span_details.parent_context
            start_time = span_details.start_time
            end_time = span_details.end_time

        super().__init__(
            kind="Client",
            operation_name=OUTPUT_OPERATION_NAME,
            activity_name=(f"{OUTPUT_OPERATION_NAME} {agent_details.agent_id}"),
            agent_details=agent_details,
            parent_context=parent_context,
            start_time=start_time,
            end_time=end_time,
        )

        self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)

        # Initialize accumulated messages list
        self._output_messages: list[str] = list(response.messages)

        # Set response messages
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(self._output_messages))

        # Set user details if provided
        if user_details:
            self.set_tag_maybe(USER_ID_KEY, user_details.user_id)
            self.set_tag_maybe(USER_EMAIL_KEY, user_details.user_email)
            self.set_tag_maybe(USER_NAME_KEY, user_details.user_name)
            self.set_tag_maybe(
                GEN_AI_CALLER_CLIENT_IP_KEY,
                validate_and_normalize_ip(user_details.user_client_ip),
            )

    def record_output_messages(self, messages: list[str]) -> None:
        """Records the output messages for telemetry tracking.

        Appends the provided messages to the accumulated output messages list.
        The list is capped at _MAX_OUTPUT_MESSAGES to prevent unbounded memory growth.

        Args:
            messages: List of output messages to append
        """
        self._output_messages.extend(messages)
        if len(self._output_messages) > self._MAX_OUTPUT_MESSAGES:
            self._output_messages = self._output_messages[-self._MAX_OUTPUT_MESSAGES :]
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(self._output_messages))

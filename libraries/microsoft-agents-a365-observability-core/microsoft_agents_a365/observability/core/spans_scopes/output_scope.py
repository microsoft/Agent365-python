# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import datetime

from opentelemetry.context import Context

from ..agent_details import AgentDetails
from ..constants import GEN_AI_OUTPUT_MESSAGES_KEY
from ..models.response import Response
from ..opentelemetry_scope import OpenTelemetryScope
from ..tenant_details import TenantDetails
from ..utils import safe_json_dumps

OUTPUT_OPERATION_NAME = "output_messages"


class OutputScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for output messages."""

    _MAX_OUTPUT_MESSAGES = 5000

    @staticmethod
    def start(
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        response: Response,
        parent_context: Context | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> "OutputScope":
        """Creates and starts a new scope for output tracing.

        Args:
            agent_details: The details of the agent
            tenant_details: The details of the tenant
            response: The response details from the agent
            parent_context: Optional OpenTelemetry Context used to link this span to an
                upstream operation. Use ``extract_context_from_headers()`` to convert a
                Context from HTTP headers containing W3C traceparent.
            start_time: Optional explicit start time as a datetime object.
            end_time: Optional explicit end time as a datetime object.

        Returns:
            A new OutputScope instance
        """
        return OutputScope(
            agent_details, tenant_details, response, parent_context, start_time, end_time
        )

    def __init__(
        self,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        response: Response,
        parent_context: Context | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        """Initialize the output scope.

        Args:
            agent_details: The details of the agent
            tenant_details: The details of the tenant
            response: The response details from the agent
            parent_context: Optional OpenTelemetry Context used to link this span to an
                upstream operation. Use ``extract_context_from_headers()`` to convert a
                Context from HTTP headers containing W3C traceparent.
            start_time: Optional explicit start time as a datetime object.
            end_time: Optional explicit end time as a datetime object.
        """
        super().__init__(
            kind="Client",
            operation_name=OUTPUT_OPERATION_NAME,
            activity_name=(f"{OUTPUT_OPERATION_NAME} {agent_details.agent_id}"),
            agent_details=agent_details,
            tenant_details=tenant_details,
            parent_context=parent_context,
            start_time=start_time,
            end_time=end_time,
        )

        # Initialize accumulated messages list
        self._output_messages: list[str] = list(response.messages)

        # Set response messages
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(self._output_messages))

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

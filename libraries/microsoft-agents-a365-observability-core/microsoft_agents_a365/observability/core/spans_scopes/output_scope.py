# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from ..agent_details import AgentDetails
from ..constants import GEN_AI_OUTPUT_MESSAGES_KEY
from ..models.response import Response
from ..opentelemetry_scope import OpenTelemetryScope
from ..tenant_details import TenantDetails
from ..utils import safe_json_dumps

OUTPUT_OPERATION_NAME = "output_messages"


class OutputScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for output messages."""

    @staticmethod
    def start(
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        response: Response,
    ) -> "OutputScope":
        """Creates and starts a new scope for output tracing.

        Args:
            agent_details: The details of the agent
            tenant_details: The details of the tenant
            response: The response details from the agent

        Returns:
            A new OutputScope instance
        """
        return OutputScope(agent_details, tenant_details, response)

    def __init__(
        self,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        response: Response,
    ):
        """Initialize the output scope.

        Args:
            agent_details: The details of the agent
            tenant_details: The details of the tenant
            response: The response details from the agent
        """
        super().__init__(
            kind="Client",
            operation_name=OUTPUT_OPERATION_NAME,
            activity_name=(f"{OUTPUT_OPERATION_NAME} {agent_details.agent_id}"),
            agent_details=agent_details,
            tenant_details=tenant_details,
        )

        # Set response messages
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(response.messages))

    def record_output_messages(self, messages: list[str]) -> None:
        """Records the output messages for telemetry tracking.

        Args:
            messages: List of output messages
        """
        self.set_tag_maybe(GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(messages))

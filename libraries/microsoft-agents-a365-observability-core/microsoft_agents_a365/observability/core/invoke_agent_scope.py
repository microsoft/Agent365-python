# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Invoke agent scope for tracing agent invocation.

from .agent_details import AgentDetails
from .constants import (
    GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY,
    GEN_AI_CALLER_AGENT_ID_KEY,
    GEN_AI_CALLER_AGENT_NAME_KEY,
    GEN_AI_CALLER_AGENT_TENANT_ID_KEY,
    GEN_AI_CALLER_AGENT_UPN_KEY,
    GEN_AI_CALLER_AGENT_USER_ID_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CALLER_NAME_KEY,
    GEN_AI_CALLER_TENANT_ID_KEY,
    GEN_AI_CALLER_UPN_KEY,
    GEN_AI_CALLER_USER_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    INVOKE_AGENT_OPERATION_NAME,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
    SESSION_ID_KEY,
)
from .invoke_agent_details import InvokeAgentDetails
from .models.caller_details import CallerDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .tenant_details import TenantDetails
from .utils import safe_json_dumps


class InvokeAgentScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for AI agent invocation operations."""

    @staticmethod
    def start(
        invoke_agent_details: InvokeAgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
        caller_agent_details: AgentDetails | None = None,
        caller_details: CallerDetails | None = None,
    ) -> "InvokeAgentScope":
        """Create and start a new scope for agent invocation tracing.

        Args:
            invoke_agent_details: The details of the agent invocation including endpoint,
                                agent information, and session context
            tenant_details: The details of the tenant
            request: Optional request details for additional context
            caller_agent_details: Optional details of the caller agent
            caller_details: Optional details of the non-agentic caller

        Returns:
            A new InvokeAgentScope instance
        """
        return InvokeAgentScope(
            invoke_agent_details, tenant_details, request, caller_agent_details, caller_details
        )

    def __init__(
        self,
        invoke_agent_details: InvokeAgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
        caller_agent_details: AgentDetails | None = None,
        caller_details: CallerDetails | None = None,
    ):
        """Initialize the agent invocation scope.

        Args:
            invoke_agent_details: The details of the agent invocation
            tenant_details: The details of the tenant
            request: Optional request details for additional context
            caller_agent_details: Optional details of the caller agent
            caller_details: Optional details of the non-agentic caller
        """
        activity_name = INVOKE_AGENT_OPERATION_NAME
        if invoke_agent_details.details.agent_name:
            activity_name = (
                f"{INVOKE_AGENT_OPERATION_NAME} {invoke_agent_details.details.agent_name}"
            )

        super().__init__(
            kind="Client",
            operation_name=INVOKE_AGENT_OPERATION_NAME,
            activity_name=activity_name,
            agent_details=invoke_agent_details.details,
            tenant_details=tenant_details,
        )

        endpoint, _, session_id = (
            invoke_agent_details.endpoint,
            invoke_agent_details.details,
            invoke_agent_details.session_id,
        )

        self.set_tag_maybe(SESSION_ID_KEY, session_id)
        if endpoint:
            self.set_tag_maybe(SERVER_ADDRESS_KEY, endpoint.hostname)

            # Only record port if it is different from 443
            if endpoint.port and endpoint.port != 443:
                self.set_tag_maybe(SERVER_PORT_KEY, endpoint.port)

        # Set request metadata if provided
        if request:
            if request.source_metadata:
                self.set_tag_maybe(GEN_AI_EXECUTION_SOURCE_ID_KEY, request.source_metadata.id)
                self.set_tag_maybe(GEN_AI_EXECUTION_SOURCE_NAME_KEY, request.source_metadata.name)
                self.set_tag_maybe(
                    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY, request.source_metadata.description
                )

            self.set_tag_maybe(
                GEN_AI_EXECUTION_TYPE_KEY,
                request.execution_type.value if request.execution_type else None,
            )

        # Set caller details tags
        if caller_details:
            self.set_tag_maybe(GEN_AI_CALLER_ID_KEY, caller_details.caller_id)
            self.set_tag_maybe(GEN_AI_CALLER_UPN_KEY, caller_details.caller_upn)
            self.set_tag_maybe(GEN_AI_CALLER_NAME_KEY, caller_details.caller_name)
            self.set_tag_maybe(GEN_AI_CALLER_USER_ID_KEY, caller_details.caller_user_id)
            self.set_tag_maybe(GEN_AI_CALLER_TENANT_ID_KEY, caller_details.tenant_id)

        # Set caller agent details tags
        if caller_agent_details:
            self.set_tag_maybe(GEN_AI_CALLER_AGENT_NAME_KEY, caller_agent_details.agent_name)
            self.set_tag_maybe(GEN_AI_CALLER_AGENT_ID_KEY, caller_agent_details.agent_id)
            self.set_tag_maybe(
                GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY, caller_agent_details.agent_blueprint_id
            )
            self.set_tag_maybe(GEN_AI_CALLER_AGENT_USER_ID_KEY, caller_agent_details.agent_auid)
            self.set_tag_maybe(GEN_AI_CALLER_AGENT_UPN_KEY, caller_agent_details.agent_upn)
            self.set_tag_maybe(GEN_AI_CALLER_AGENT_TENANT_ID_KEY, caller_agent_details.tenant_id)

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

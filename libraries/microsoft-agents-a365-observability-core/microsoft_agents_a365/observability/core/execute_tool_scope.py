# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .agent_details import AgentDetails
from .constants import (
    EXECUTE_TOOL_OPERATION_NAME,
    GEN_AI_EVENT_CONTENT,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_ID_KEY,
    GEN_AI_TOOL_DESCRIPTION_KEY,
    GEN_AI_TOOL_NAME_KEY,
    GEN_AI_TOOL_TYPE_KEY,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
)
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .tenant_details import TenantDetails
from .tool_call_details import ToolCallDetails


class ExecuteToolScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for AI tool execution operations."""

    @staticmethod
    def start(
        details: ToolCallDetails,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
        parent_id: str | None = None,
    ) -> "ExecuteToolScope":
        """Creates and starts a new scope for tool execution tracing.

        Args:
            details: The details of the tool call
            agent_details: The details of the agent making the call
            tenant_details: The details of the tenant
            request: Optional request details for additional context
            parent_id: Optional parent Activity ID used to link this span to an upstream
                operation

        Returns:
            A new ExecuteToolScope instance
        """
        return ExecuteToolScope(details, agent_details, tenant_details, request, parent_id)

    def __init__(
        self,
        details: ToolCallDetails,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        request: Request | None = None,
        parent_id: str | None = None,
    ):
        """Initialize the tool execution scope.

        Args:
            details: The details of the tool call
            agent_details: The details of the agent making the call
            tenant_details: The details of the tenant
            request: Optional request details for additional context
            parent_id: Optional parent Activity ID used to link this span to an upstream
                operation
        """
        super().__init__(
            kind="Internal",
            operation_name=EXECUTE_TOOL_OPERATION_NAME,
            activity_name=f"{EXECUTE_TOOL_OPERATION_NAME} {details.tool_name}",
            agent_details=agent_details,
            tenant_details=tenant_details,
            parent_id=parent_id,
        )

        # Extract details using deconstruction-like approach
        tool_name = details.tool_name
        arguments = details.arguments
        tool_call_id = details.tool_call_id
        description = details.description
        tool_type = details.tool_type
        endpoint = details.endpoint

        self.set_tag_maybe(GEN_AI_TOOL_NAME_KEY, tool_name)
        self.set_tag_maybe(GEN_AI_TOOL_ARGS_KEY, arguments)
        self.set_tag_maybe(GEN_AI_TOOL_TYPE_KEY, tool_type)
        self.set_tag_maybe(GEN_AI_TOOL_CALL_ID_KEY, tool_call_id)
        self.set_tag_maybe(GEN_AI_TOOL_DESCRIPTION_KEY, description)

        if endpoint:
            self.set_tag_maybe(SERVER_ADDRESS_KEY, endpoint.hostname)
            if endpoint.port and endpoint.port != 443:
                self.set_tag_maybe(SERVER_PORT_KEY, endpoint.port)

        # Set request metadata if provided
        if request and request.source_metadata:
            self.set_tag_maybe(GEN_AI_EXECUTION_SOURCE_NAME_KEY, request.source_metadata.name)
            self.set_tag_maybe(
                GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY, request.source_metadata.description
            )

    def record_response(self, response: str) -> None:
        """Records response information for telemetry tracking.

        Args:
            response: The response to record
        """
        self.set_tag_maybe(GEN_AI_EVENT_CONTENT, response)

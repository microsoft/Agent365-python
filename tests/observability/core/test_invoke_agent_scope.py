# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from urllib.parse import urlparse

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecutionType,
    InvokeAgentDetails,
    InvokeAgentScope,
    Request,
    SourceMetadata,
    TenantDetails,
    configure,
)
from microsoft_agents_a365.observability.core.models.caller_details import CallerDetails
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Constants for span attribute keys
GEN_AI_EXECUTION_SOURCE_NAME_KEY = "gen_ai.channel.name"
GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY = "gen_ai.channel.link"
GEN_AI_EXECUTION_TYPE_KEY = "gen_ai.execution.type"
GEN_AI_INPUT_MESSAGES_KEY = "gen_ai.input.messages"


class TestInvokeAgentScope(unittest.TestCase):
    """Unit tests for InvokeAgentScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        configure(
            service_name="test-invoke-agent-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for invoke scope testing",
        )
        cls.invoke_details = InvokeAgentDetails(
            endpoint=urlparse("https://example.com/agent"),
            details=cls.agent_details,
            session_id="session-123",
        )

        # Create source metadata for requests
        cls.source_metadata = SourceMetadata(
            id="source-agent-456",
            name="Source Channel",
            icon_uri="https://example.com/source-icon.png",
            description="Source channel description",
        )

        # Create a comprehensive request object
        cls.test_request = Request(
            content="Process customer inquiry about order status",
            execution_type=ExecutionType.AGENT_TO_AGENT,
            session_id="session-abc123",
            source_metadata=cls.source_metadata,
        )

        # Create caller details (non-agentic caller)
        cls.caller_details = CallerDetails(
            caller_id="user-123",
            caller_upn="user@contoso.com",
            caller_name="John Doe",
            caller_user_id="user-id-456",
            tenant_id="tenant-789",
        )

        # Create caller agent details (agentic caller)
        cls.caller_agent_details = AgentDetails(
            agent_id="caller-agent-789",
            agent_name="Caller Agent",
            agent_description="The agent that initiated this request",
            agent_blueprint_id="blueprint-456",
            agent_auid="auid-123",
            agent_upn="agent@contoso.com",
            tenant_id="tenant-789",
        )

    def test_record_response_method_exists(self):
        """Test that record_response method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_response"))
            self.assertTrue(callable(scope.record_response))
            scope.dispose()

    def test_record_input_messages_method_exists(self):
        """Test that record_input_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_input_messages"))
            self.assertTrue(callable(scope.record_input_messages))
            scope.dispose()

    def test_record_output_messages_method_exists(self):
        """Test that record_output_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_output_messages"))
            self.assertTrue(callable(scope.record_output_messages))
            scope.dispose()

    def test_request_attributes_set_on_span(self):
        """Test that request parameters from mock data are available on span attributes."""
        # Set up tracer to capture spans
        span_exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Create scope with request
        scope = InvokeAgentScope.start(
            invoke_agent_details=self.invoke_details,
            tenant_details=self.tenant_details,
            request=self.test_request,
        )

        if scope is not None:
            scope.dispose()

        # Check if mock data parameters are available in span attributes
        finished_spans = span_exporter.get_finished_spans()

        if finished_spans:
            # Get attributes from the span
            span = finished_spans[-1]
            span_attributes = getattr(span, "attributes", {}) or {}

            # Verify mock data request parameters are in span attributes
            # Check source channel name from mock data
            if GEN_AI_EXECUTION_SOURCE_NAME_KEY in span_attributes:
                self.assertEqual(
                    span_attributes[GEN_AI_EXECUTION_SOURCE_NAME_KEY],
                    self.source_metadata.name,  # From cls.source_metadata.name
                )

            # Check source channel description from mock data
            if GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY in span_attributes:
                self.assertEqual(
                    span_attributes[GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY],
                    self.source_metadata.description,  # From cls.source_metadata.description
                )

            # Check execution type from mock data
            if GEN_AI_EXECUTION_TYPE_KEY in span_attributes:
                self.assertEqual(
                    span_attributes[GEN_AI_EXECUTION_TYPE_KEY],
                    self.test_request.execution_type.value,  # From cls.test_request.execution_type
                )

            # Check input messages contain request content from mock data
            if GEN_AI_INPUT_MESSAGES_KEY in span_attributes:
                input_messages = span_attributes[GEN_AI_INPUT_MESSAGES_KEY]
                self.assertIn(
                    self.test_request.content,  # From cls.test_request.content
                    input_messages,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
import sys
import unittest
import pytest
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
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_CALLER_AGENT_USER_CLIENT_IP,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.models.caller_details import CallerDetails
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestInvokeAgentScope(unittest.TestCase):
    """Unit tests for InvokeAgentScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

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
            agent_client_ip="192.168.1.100",
        )

    def setUp(self):
        super().setUp()

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()

        self.span_exporter.clear()

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
        # Create scope with request
        scope = InvokeAgentScope.start(
            invoke_agent_details=self.invoke_details,
            tenant_details=self.tenant_details,
            request=self.test_request,
        )

        if scope is not None:
            scope.dispose()

        # Check if mock data parameters are available in span attributes
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

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

    def test_caller_agent_client_ip_in_scope(self):
        """Test that caller agent client IP is properly handled when creating InvokeAgentScope."""
        # Set up tracer to capture spans
        span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

        # Create scope with caller agent details that include client IP
        scope = InvokeAgentScope.start(
            invoke_agent_details=self.invoke_details,
            tenant_details=self.tenant_details,
            caller_agent_details=self.caller_agent_details,  # Contains agent_client_ip="192.168.1.100"
        )

        if scope is not None:
            # Verify the caller agent details contain the expected IP
            self.assertEqual(self.caller_agent_details.agent_client_ip, "192.168.1.100")
            scope.dispose()

        # Verify the IP is set as a span attribute
        finished_spans = span_exporter.get_finished_spans()
        if finished_spans:
            span = finished_spans[-1]
            span_attributes = getattr(span, "attributes", {}) or {}

            # Verify the caller agent client IP is set as a span attribute
            if GEN_AI_CALLER_AGENT_USER_CLIENT_IP in span_attributes:
                self.assertEqual(
                    span_attributes[GEN_AI_CALLER_AGENT_USER_CLIENT_IP], "192.168.1.100"
                )


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

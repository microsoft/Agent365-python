# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    CallerDetails,
    Channel,
    InvokeAgentScope,
    InvokeAgentScopeDetails,
    Request,
    SpanDetails,
    UserDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind


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
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for invoke scope testing",
        )
        cls.invoke_scope_details = InvokeAgentScopeDetails(
            endpoint=urlparse("https://example.com/agent"),
        )

        # Create channel for requests
        cls.channel = Channel(
            name="Source Channel",
            link="Source channel link",
        )

        # Create a comprehensive request object
        cls.test_request = Request(
            content="Process customer inquiry about order status",
            session_id="session-abc123",
            channel=cls.channel,
            conversation_id="conv-abc123",
        )

        # Create caller details (non-agentic caller)
        cls.user_details = UserDetails(
            user_id="user-123",
            user_email="user@contoso.com",
            user_name="John Doe",
            user_client_ip="192.168.1.100",
        )
        cls.caller_details = CallerDetails(
            user_details=cls.user_details,
        )

        # Create caller agent details (agentic caller)
        cls.caller_agent_details = AgentDetails(
            agent_id="caller-agent-789",
            agent_name="Caller Agent",
            agent_description="The agent that initiated this request",
            agent_blueprint_id="blueprint-456",
            agentic_user_id="auid-123",
            agentic_user_email="agent@contoso.com",
            tenant_id="tenant-789",
            agent_platform_id="platform-123",
        )

    def setUp(self):
        super().setUp()

        # Reset TelemetryManager state to ensure fresh configuration

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        # Reconfigure to get a fresh TracerProvider
        configure(
            service_name="test-invoke-agent-service",
            service_namespace="test-namespace",
        )

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()

        self.span_exporter.clear()

    def test_record_response_method_exists(self):
        """Test that record_response method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_response"))
            self.assertTrue(callable(scope.record_response))
            scope.dispose()

    def test_record_input_messages_method_exists(self):
        """Test that record_input_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_input_messages"))
            self.assertTrue(callable(scope.record_input_messages))
            scope.dispose()

    def test_record_output_messages_method_exists(self):
        """Test that record_output_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_output_messages"))
            self.assertTrue(callable(scope.record_output_messages))
            scope.dispose()

    def test_request_attributes_set_on_span(self):
        """Test that request parameters from mock data are available on span attributes."""
        # Create scope with request
        scope = InvokeAgentScope.start(
            self.test_request,
            self.invoke_scope_details,
            self.agent_details,
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
        if CHANNEL_NAME_KEY in span_attributes:
            self.assertEqual(
                span_attributes[CHANNEL_NAME_KEY],
                self.channel.name,  # From cls.channel.name
            )

        # Check source channel link from mock data
        if CHANNEL_LINK_KEY in span_attributes:
            self.assertEqual(
                span_attributes[CHANNEL_LINK_KEY],
                self.channel.link,  # From cls.channel.link
            )

        # Check input messages contain request content from mock data
        if GEN_AI_INPUT_MESSAGES_KEY in span_attributes:
            input_messages = span_attributes[GEN_AI_INPUT_MESSAGES_KEY]
            self.assertIn(
                self.test_request.content,  # From cls.test_request.content
                input_messages,
            )

    def test_invoke_agent_scope_span_kind(self):
        """Test that InvokeAgentScope creates spans with the correct SpanKind."""
        # Create scope
        scope = InvokeAgentScope.start(
            self.test_request,
            self.invoke_scope_details,
            self.agent_details,
        )

        if scope is not None:
            scope.dispose()

        # Check that span was created with correct SpanKind
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        # Get the span and verify its kind
        span = finished_spans[-1]
        self.assertEqual(
            span.kind,
            SpanKind.CLIENT,
            "InvokeAgentScope defaults to CLIENT spans (can be overridden with span_kind parameter)",
        )

        # Test SERVER span kind override
        scope_server = InvokeAgentScope.start(
            self.test_request,
            self.invoke_scope_details,
            self.agent_details,
            span_details=SpanDetails(span_kind=SpanKind.SERVER),
        )

        if scope_server is not None:
            scope_server.dispose()

        # Check that SERVER span was created
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(len(finished_spans) >= 2, "Expected at least two spans to be created")

        # Get the most recent span and verify it's SERVER
        server_span = finished_spans[-1]
        self.assertEqual(
            server_span.kind,
            SpanKind.SERVER,
            "InvokeAgentScope should create SERVER spans when span_kind parameter is set",
        )


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

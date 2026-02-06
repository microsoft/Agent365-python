# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import unittest
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    TenantDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.constants import (
    CUSTOM_PARENT_SPAN_ID_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestOutputScope(unittest.TestCase):
    """Unit tests for OutputScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-output-scope-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for output scope testing",
        )

    def setUp(self):
        super().setUp()

        # Reset TelemetryManager state to ensure fresh configuration
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        # Reconfigure to get a fresh TracerProvider
        configure(
            service_name="test-output-scope-service",
            service_namespace="test-namespace",
        )

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def test_output_scope_creation(self):
        """Test that OutputScope can be created successfully."""
        response = Response(messages=["Hello, how can I help you?"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        self.assertIsNotNone(scope)
        scope.dispose()

    def test_record_output_messages_method_exists(self):
        """Test that record_output_messages method exists on OutputScope."""
        response = Response(messages=["Initial message"])
        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_output_messages"))
            self.assertTrue(callable(scope.record_output_messages))
            scope.dispose()

    def test_output_messages_set_on_span(self):
        """Test that output messages are set on span attributes."""
        response = Response(messages=["This is the agent response"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            GEN_AI_OUTPUT_MESSAGES_KEY,
            span_attributes,
            "Expected output messages key to be set on span",
        )

        # Verify the message content is in the serialized output
        output_value = span_attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
        self.assertIn("This is the agent response", output_value)

    def test_multiple_output_messages(self):
        """Test that multiple output messages are properly recorded."""
        response = Response(messages=["First response", "Second response", "Third response"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            GEN_AI_OUTPUT_MESSAGES_KEY,
            span_attributes,
            "Expected output messages key to be set on span",
        )

        output_value = span_attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
        self.assertIn("First response", output_value)
        self.assertIn("Second response", output_value)
        self.assertIn("Third response", output_value)

    def test_record_output_messages_updates_span(self):
        """Test that record_output_messages updates the span with new messages."""
        response = Response(messages=["Initial message"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            # Record updated messages
            scope.record_output_messages(["Updated message 1", "Updated message 2"])
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            GEN_AI_OUTPUT_MESSAGES_KEY,
            span_attributes,
            "Expected output messages key to be set on span",
        )

        # The span should have the updated messages
        output_value = span_attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
        self.assertIn("Updated message 1", output_value)
        self.assertIn("Updated message 2", output_value)

    def test_output_scope_context_manager(self):
        """Test that OutputScope works as a context manager."""
        response = Response(messages=["Context manager test"])

        with OutputScope.start(self.agent_details, self.tenant_details, response) as scope:
            self.assertIsNotNone(scope)

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

    def test_output_scope_span_name(self):
        """Test that OutputScope creates spans with correct operation name."""
        response = Response(messages=["Test message"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        # The activity name should contain "output_messages" and the agent id
        self.assertIn("output_messages", span.name)
        self.assertIn(self.agent_details.agent_id, span.name)

    def test_output_scope_with_parent_id(self):
        """Test that OutputScope records parent_id when provided."""
        response = Response(messages=["Test message with parent"])
        parent_id = "00-1234567890abcdef1234567890abcdef-abcdefabcdef1234-01"

        scope = OutputScope.start(
            self.agent_details, self.tenant_details, response, parent_id=parent_id
        )

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        # Verify the parent ID is set as a span attribute
        self.assertIn(
            CUSTOM_PARENT_SPAN_ID_KEY,
            span_attributes,
            "Expected custom parent span ID to be set on span",
        )
        self.assertEqual(span_attributes[CUSTOM_PARENT_SPAN_ID_KEY], parent_id)

    def test_output_scope_without_parent_id(self):
        """Test that OutputScope doesn't set parent_id attribute when not provided."""
        response = Response(messages=["Test message without parent"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        # Verify the parent ID attribute is NOT set when not provided
        self.assertNotIn(
            CUSTOM_PARENT_SPAN_ID_KEY,
            span_attributes,
            "Expected custom parent span ID NOT to be set when not provided",
        )


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

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
from microsoft_agents_a365.observability.core.constants import GEN_AI_OUTPUT_MESSAGES_KEY
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestOutputScope(unittest.TestCase):
    """Unit tests for OutputScope."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-output-scope-service",
            service_namespace="test-namespace",
        )

        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for output scope testing",
        )

    def setUp(self):
        super().setUp()

        # Reset TelemetryManager state
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        configure(
            service_name="test-output-scope-service",
            service_namespace="test-namespace",
        )

        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def _get_last_span(self):
        """Helper to get the last finished span and its attributes."""
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")
        span = finished_spans[-1]
        attributes = getattr(span, "attributes", {}) or {}
        return span, attributes

    def test_output_scope_creates_span_with_messages(self):
        """Test OutputScope creates span with output messages attribute."""
        response = Response(messages=["First message", "Second message"])

        with OutputScope.start(self.agent_details, self.tenant_details, response):
            pass

        span, attributes = self._get_last_span()

        # Verify span name contains operation name and agent id
        self.assertIn("output_messages", span.name)
        self.assertIn(self.agent_details.agent_id, span.name)

        # Verify output messages are set
        self.assertIn(GEN_AI_OUTPUT_MESSAGES_KEY, attributes)
        output_value = attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
        self.assertIn("First message", output_value)
        self.assertIn("Second message", output_value)

    def test_record_output_messages_appends(self):
        """Test record_output_messages appends to accumulated messages."""
        response = Response(messages=["Initial"])

        with OutputScope.start(self.agent_details, self.tenant_details, response) as scope:
            scope.record_output_messages(["Appended 1"])
            scope.record_output_messages(["Appended 2", "Appended 3"])

        _, attributes = self._get_last_span()

        output_value = attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
        # All messages should be present (initial + all appended)
        self.assertIn("Initial", output_value)
        self.assertIn("Appended 1", output_value)
        self.assertIn("Appended 2", output_value)
        self.assertIn("Appended 3", output_value)

    def test_output_scope_with_parent_id(self):
        """Test OutputScope uses parent_id to link span to parent context."""
        response = Response(messages=["Test"])
        parent_trace_id = "1234567890abcdef1234567890abcdef"
        parent_span_id = "abcdefabcdef1234"
        parent_id = f"00-{parent_trace_id}-{parent_span_id}-01"

        with OutputScope.start(
            self.agent_details, self.tenant_details, response, parent_id=parent_id
        ):
            pass

        span, _ = self._get_last_span()

        # Verify span inherits parent's trace_id
        span_trace_id = f"{span.context.trace_id:032x}"
        self.assertEqual(span_trace_id, parent_trace_id)

        # Verify span's parent_span_id matches
        self.assertIsNotNone(span.parent, "Expected span to have a parent")
        self.assertTrue(hasattr(span.parent, "span_id"), "Expected parent to have span_id")
        span_parent_id = f"{span.parent.span_id:016x}"
        self.assertEqual(span_parent_id, parent_span_id)

    def test_output_scope_dispose(self):
        """Test OutputScope dispose method ends the span."""
        response = Response(messages=["Test"])

        scope = OutputScope.start(self.agent_details, self.tenant_details, response)
        self.assertIsNotNone(scope)
        scope.dispose()

        # Verify span was created and ended
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertEqual(len(finished_spans), 1)


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

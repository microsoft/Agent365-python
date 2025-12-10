# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
import sys
import unittest
import pytest

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecutionType,
    ExecuteToolScope,
    Request,
    SourceMetadata,
    TenantDetails,
    ToolCallDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
)
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestExecuteToolScope(unittest.TestCase):
    """Unit tests for ExecuteToolScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-execute-tool-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for tool execution testing",
        )
        cls.tool_details = ToolCallDetails(
            tool_name="weather_tool",
            arguments='{"location": "Seattle", "units": "metric"}',
            tool_call_id="call-123",
            description="Get current weather information for a location",
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
        """Test that record_response method exists on ExecuteToolScope."""
        scope = ExecuteToolScope.start(self.tool_details, self.agent_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_response"))
            self.assertTrue(callable(scope.record_response))
            scope.dispose()

    def test_request_metadata_set_on_span(self):
        """Test that request source metadata is set on span attributes."""
        request = Request(
            content="Execute tool with request metadata",
            execution_type=ExecutionType.AGENT_TO_AGENT,
            session_id="session-xyz",
            source_metadata=SourceMetadata(name="Channel 1", description="Link to channel"),
        )

        scope = ExecuteToolScope.start(
            self.tool_details, self.agent_details, self.tenant_details, request
        )

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            GEN_AI_EXECUTION_SOURCE_NAME_KEY,
            span_attributes,
            "Expected source name to be set on span",
        )
        self.assertEqual(
            span_attributes[GEN_AI_EXECUTION_SOURCE_NAME_KEY],
            request.source_metadata.name,
        )

        self.assertIn(
            GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
            span_attributes,
            "Expected source description to be set on span",
        )
        self.assertEqual(
            span_attributes[GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY],
            request.source_metadata.description,
        )


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

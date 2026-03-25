# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for trace context propagation functionality."""

import os
import unittest
from urllib.parse import urlparse

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecuteToolScope,
    InferenceCallDetails,
    InferenceOperationType,
    InferenceScope,
    InvokeAgentScope,
    InvokeAgentScopeDetails,
    Request,
    SpanDetails,
    ToolCallDetails,
    configure,
    extract_context_from_headers,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestTraceContextPropagation(unittest.TestCase):
    """Unit tests for trace context propagation functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-trace-propagation-service",
            service_namespace="test-namespace",
        )

        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for trace propagation testing",
        )

    def setUp(self):
        super().setUp()

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        configure(
            service_name="test-trace-propagation-service",
            service_namespace="test-namespace",
        )

        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def test_inject_context_to_headers_returns_headers(self):
        """Test that inject_context_to_headers returns traceparent and tracestate headers."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            headers = scope.inject_context_to_headers()

            # Should contain at least traceparent header
            self.assertIn("traceparent", headers)

            # Validate traceparent format: 00-{trace_id}-{span_id}-{flags}
            traceparent = headers["traceparent"]
            parts = traceparent.split("-")
            self.assertEqual(len(parts), 4, "traceparent should have 4 parts")
            self.assertEqual(parts[0], "00", "version should be 00")
            self.assertEqual(len(parts[1]), 32, "trace_id should be 32 hex chars")
            self.assertEqual(len(parts[2]), 16, "span_id should be 16 hex chars")
            self.assertEqual(len(parts[3]), 2, "flags should be 2 hex chars")

            scope.dispose()

    def test_inject_context_to_headers_contains_span_id(self):
        """Test that injected headers contain the correct span ID."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            headers = scope.inject_context_to_headers()
            scope.dispose()

            # Get the span from exported spans
            finished_spans = self.span_exporter.get_finished_spans()
            self.assertTrue(finished_spans, "Expected at least one span to be created")

            span = finished_spans[-1]
            expected_span_id = f"{span.context.span_id:016x}"

            # Verify the traceparent contains the span_id
            traceparent = headers["traceparent"]
            parts = traceparent.split("-")
            self.assertEqual(parts[2], expected_span_id)

    def test_get_context_returns_context_object(self):
        """Test that get_context returns a valid Context object."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            ctx = scope.get_context()

            # Should return a Context object
            self.assertIsNotNone(ctx)

            scope.dispose()

    def test_context_propagation_via_inject_extract(self):
        """Test that context can be propagated using inject/extract pattern."""
        # Create parent scope
        parent_details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        parent_scope = InferenceScope.start(Request(), parent_details, self.agent_details)

        # Get injected headers from parent
        headers = parent_scope.inject_context_to_headers()
        parent_scope.dispose()

        # Extract context from headers (simulating receiving via HTTP)
        parent_context = extract_context_from_headers(headers)

        # Create child scope using extracted context
        tool_details = ToolCallDetails(
            tool_name="search_tool",
            arguments='{"query": "test"}',
            tool_call_id="call-123",
        )

        child_scope = ExecuteToolScope.start(
            Request(),
            tool_details,
            self.agent_details,
            span_details=SpanDetails(parent_context=parent_context),
        )
        child_scope.dispose()

        # Verify parent-child relationship
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertEqual(len(finished_spans), 2, "Expected 2 spans (parent and child)")

        parent_span = finished_spans[0]
        child_span = finished_spans[1]

        # Child should have parent's trace_id
        self.assertEqual(
            parent_span.context.trace_id,
            child_span.context.trace_id,
            "Child span should have same trace_id as parent",
        )

        # Child's parent should be the parent span
        self.assertIsNotNone(child_span.parent)
        self.assertEqual(
            child_span.parent.span_id,
            parent_span.context.span_id,
            "Child's parent_id should match parent's span_id",
        )

    def test_inject_headers_for_http_propagation(self):
        """Test that injected headers can be used for HTTP request propagation."""
        # Create a scope
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            headers = scope.inject_context_to_headers()
            scope.dispose()

            # Simulate receiving these headers and creating a child scope
            parent_ctx = extract_context_from_headers(headers)

            # Create new scope using received context
            child_details = InferenceCallDetails(
                operationName=InferenceOperationType.TEXT_COMPLETION,
                model="gpt-3.5-turbo",
                providerName="openai",
            )

            child_scope = InferenceScope.start(
                Request(),
                child_details,
                self.agent_details,
                span_details=SpanDetails(parent_context=parent_ctx),
            )
            if child_scope is not None:
                child_scope.dispose()

            # Verify spans are properly linked
            finished_spans = self.span_exporter.get_finished_spans()
            self.assertEqual(len(finished_spans), 2)

            parent_span = finished_spans[0]
            child_span = finished_spans[1]

            # Should have same trace_id
            self.assertEqual(
                f"{parent_span.context.trace_id:032x}",
                f"{child_span.context.trace_id:032x}",
            )

    def test_invoke_agent_scope_with_parent_context(self):
        """Test InvokeAgentScope with parent_context parameter."""
        parent_trace_id = "1234567890abcdef1234567890abcdef"
        parent_span_id = "abcdefabcdef1234"
        traceparent = f"00-{parent_trace_id}-{parent_span_id}-01"

        parent_context = extract_context_from_headers({"traceparent": traceparent})

        invoke_scope_details = InvokeAgentScopeDetails(
            endpoint=urlparse("https://example.com/agent"),
        )

        with InvokeAgentScope.start(
            Request(),
            invoke_scope_details,
            self.agent_details,
            span_details=SpanDetails(parent_context=parent_context),
        ) as scope:
            headers = scope.inject_context_to_headers()
            self.assertIn("traceparent", headers)

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]

        # Verify span inherits parent's trace_id
        span_trace_id = f"{span.context.trace_id:032x}"
        self.assertEqual(span_trace_id, parent_trace_id)

        # Verify span's parent_span_id matches
        self.assertIsNotNone(span.parent, "Expected span to have a parent")
        span_parent_id = f"{span.parent.span_id:016x}"
        self.assertEqual(span_parent_id, parent_span_id)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

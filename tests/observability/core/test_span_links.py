# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import unittest
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecuteToolScope,
    InferenceCallDetails,
    InferenceOperationType,
    InvokeAgentScope,
    Request,
    SpanDetails,
    ToolCallDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.invoke_agent_details import InvokeAgentScopeDetails
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Link, SpanContext, TraceFlags


class TestSpanLinks(unittest.TestCase):
    """Tests that span links are correctly forwarded to OTel spans on all scope types."""

    @classmethod
    def setUpClass(cls):
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"
        configure(
            service_name="test-span-links-service",
            service_namespace="test-namespace",
        )

        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent",
            tenant_id="test-tenant-456",
        )
        cls.test_request = Request(conversation_id="test-conv-123")

        cls.sample_links = [
            Link(
                context=SpanContext(
                    trace_id=int("0aa4621e5ae09963a3de354f3d18aa65", 16),
                    span_id=int("c1aaa519600b1bf0", 16),
                    is_remote=True,
                    trace_flags=TraceFlags.SAMPLED,
                ),
            ),
            Link(
                context=SpanContext(
                    trace_id=int("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", 16),
                    span_id=int("aaaaaaaaaaaaaaaa", 16),
                    is_remote=True,
                    trace_flags=TraceFlags.DEFAULT,
                ),
                attributes={"link.reason": "retry"},
            ),
        ]

    def setUp(self):
        super().setUp()
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        configure(
            service_name="test-span-links-service",
            service_namespace="test-namespace",
        )
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def _get_last_span(self):
        spans = self.span_exporter.get_finished_spans()
        self.assertTrue(spans, "Expected at least one span")
        return spans[-1]

    def test_execute_tool_scope_records_span_links(self):
        """Test span links are recorded on ExecuteToolScope spans."""
        tool_details = ToolCallDetails(tool_name="my-tool")
        scope = ExecuteToolScope.start(
            self.test_request,
            tool_details,
            self.agent_details,
            span_details=SpanDetails(span_links=self.sample_links),
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 2)
        self.assertEqual(
            f"{span.links[0].context.trace_id:032x}", "0aa4621e5ae09963a3de354f3d18aa65"
        )
        self.assertEqual(f"{span.links[0].context.span_id:016x}", "c1aaa519600b1bf0")
        self.assertEqual(span.links[0].context.trace_flags, TraceFlags.SAMPLED)
        self.assertEqual(
            f"{span.links[1].context.trace_id:032x}", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )
        self.assertEqual(span.links[1].attributes.get("link.reason"), "retry")

    def test_invoke_agent_scope_records_span_links(self):
        """Test span links are recorded on InvokeAgentScope spans."""
        scope = InvokeAgentScope.start(
            self.test_request,
            InvokeAgentScopeDetails(),
            self.agent_details,
            span_details=SpanDetails(span_links=self.sample_links),
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 2)
        self.assertEqual(
            f"{span.links[0].context.trace_id:032x}", "0aa4621e5ae09963a3de354f3d18aa65"
        )

    def test_inference_scope_records_span_links(self):
        """Test span links are recorded on InferenceScope spans."""
        from microsoft_agents_a365.observability.core import InferenceScope

        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )
        scope = InferenceScope.start(
            self.test_request,
            details,
            self.agent_details,
            span_details=SpanDetails(span_links=self.sample_links),
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 2)
        self.assertEqual(
            f"{span.links[0].context.trace_id:032x}", "0aa4621e5ae09963a3de354f3d18aa65"
        )

    def test_output_scope_records_span_links(self):
        """Test span links are recorded on OutputScope spans."""
        response = Response(messages=["hello"])
        scope = OutputScope.start(
            self.test_request,
            response,
            self.agent_details,
            span_details=SpanDetails(span_links=self.sample_links),
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 2)
        self.assertEqual(
            f"{span.links[0].context.trace_id:032x}", "0aa4621e5ae09963a3de354f3d18aa65"
        )

    def test_no_span_links_when_omitted(self):
        """Test spans have empty links when span_links is not provided."""
        tool_details = ToolCallDetails(tool_name="my-tool")
        scope = ExecuteToolScope.start(
            self.test_request,
            tool_details,
            self.agent_details,
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 0)

    def test_span_links_with_typed_attributes(self):
        """Test span links preserve typed attributes (string, int)."""
        links_with_attrs = [
            Link(
                context=SpanContext(
                    trace_id=int("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 16),
                    span_id=int("bbbbbbbbbbbbbbbb", 16),
                    is_remote=True,
                    trace_flags=TraceFlags.SAMPLED,
                ),
                attributes={"link.type": "causal", "link.index": 0},
            ),
        ]

        scope = InvokeAgentScope.start(
            self.test_request,
            InvokeAgentScopeDetails(),
            self.agent_details,
            span_details=SpanDetails(span_links=links_with_attrs),
        )
        scope.dispose()

        span = self._get_last_span()
        self.assertEqual(len(span.links), 1)
        self.assertEqual(span.links[0].attributes.get("link.type"), "causal")
        self.assertEqual(span.links[0].attributes.get("link.index"), 0)


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

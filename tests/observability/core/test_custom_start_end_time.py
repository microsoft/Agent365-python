# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for custom start and end time support on OpenTelemetry scopes."""

import os
import sys
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecuteToolScope,
    Request,
    SpanDetails,
    ToolCallDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestCustomStartEndTime(unittest.TestCase):
    """Unit tests for custom start and end time support."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-custom-time-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for custom time testing",
        )
        cls.tool_details = ToolCallDetails(
            tool_name="test_tool",
            arguments='{"arg": "value"}',
            tool_call_id="call-123",
        )

    def setUp(self):
        super().setUp()

        # Reset TelemetryManager state to ensure fresh configuration
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        # Reconfigure to get a fresh TracerProvider
        configure(
            service_name="test-custom-time-service",
            service_namespace="test-namespace",
        )

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def _get_finished_span(self):
        """Get the last finished span from the exporter."""
        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")
        return finished_spans[-1]

    def test_custom_start_and_end_time_with_datetime(self):
        """Test that datetime objects are correctly converted to span timestamps."""
        custom_start = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        custom_end = datetime(2023, 11, 14, 22, 13, 25, tzinfo=UTC)  # 5 seconds later

        scope = ExecuteToolScope.start(
            Request(),
            self.tool_details,
            self.agent_details,
            span_details=SpanDetails(start_time=custom_start, end_time=custom_end),
        )
        scope.dispose()

        span = self._get_finished_span()

        expected_start_ns = int(custom_start.timestamp() * 1_000_000_000)
        expected_end_ns = int(custom_end.timestamp() * 1_000_000_000)

        span_start_ns = span.start_time
        span_end_ns = span.end_time

        self.assertAlmostEqual(span_start_ns, expected_start_ns, delta=1000)
        self.assertAlmostEqual(span_end_ns, expected_end_ns, delta=1000)

    def test_set_end_time_overrides_end_time(self):
        """Test that set_end_time overrides the end time when called before dispose."""
        custom_start = datetime(2023, 11, 14, 22, 13, 40, tzinfo=UTC)
        initial_end = datetime(2023, 11, 14, 22, 13, 45, tzinfo=UTC)  # 5 seconds after start
        later_end = datetime(2023, 11, 14, 22, 13, 48, tzinfo=UTC)  # 8 seconds after start

        scope = ExecuteToolScope.start(
            Request(),
            self.tool_details,
            self.agent_details,
            span_details=SpanDetails(start_time=custom_start, end_time=initial_end),
        )
        # Override the end time
        scope.set_end_time(later_end)
        scope.dispose()

        span = self._get_finished_span()

        expected_end_ns = int(later_end.timestamp() * 1_000_000_000)
        span_end_ns = span.end_time
        self.assertAlmostEqual(span_end_ns, expected_end_ns, delta=1000)

    def test_wall_clock_time_used_when_no_custom_times(self):
        """Test that wall-clock time is used when no custom times are provided."""
        before = time.time_ns()
        scope = ExecuteToolScope.start(
            Request(),
            self.tool_details,
            self.agent_details,
        )
        scope.dispose()
        after = time.time_ns()

        span = self._get_finished_span()

        span_start_ns = span.start_time
        span_end_ns = span.end_time

        # Span times should be within the before/after window
        # Allow some tolerance for processing time
        self.assertGreaterEqual(span_start_ns, before - 1_000_000)  # 1ms tolerance
        self.assertLessEqual(span_end_ns, after + 1_000_000)

    def test_only_start_time_provided(self):
        """Test that only custom start time can be provided without end time."""
        custom_start = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)

        scope = ExecuteToolScope.start(
            Request(),
            self.tool_details,
            self.agent_details,
            span_details=SpanDetails(start_time=custom_start),
        )
        scope.dispose()

        span = self._get_finished_span()

        expected_start_ns = int(custom_start.timestamp() * 1_000_000_000)
        span_start_ns = span.start_time

        # Start time should match what we provided
        self.assertAlmostEqual(span_start_ns, expected_start_ns, delta=1000)

        # End time should be close to current time (not custom)
        span_end_ns = span.end_time
        self.assertGreater(span_end_ns, span_start_ns)


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

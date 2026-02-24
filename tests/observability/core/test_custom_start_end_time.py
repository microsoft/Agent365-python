# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for custom start and end time support on OpenTelemetry scopes."""

import os
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecuteToolScope,
    TenantDetails,
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
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
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

    def test_custom_start_and_end_time_with_nanoseconds(self):
        """Test that constructor-provided start and end times are recorded on the span."""
        # Use nanoseconds since epoch
        custom_start_ns = 1700000000000000000  # 2023-11-14T22:13:20Z
        custom_end_ns = 1700000005000000000  # 5 seconds later

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start_ns,
            end_time=custom_end_ns,
        )
        scope.dispose()

        span = self._get_finished_span()

        # OTel Python SDK stores times as nanoseconds (int)
        span_start_ns = span.start_time
        span_end_ns = span.end_time

        # Verify start and end times are close to what we provided
        self.assertAlmostEqual(span_start_ns, custom_start_ns, delta=1000)  # 1μs tolerance
        self.assertAlmostEqual(span_end_ns, custom_end_ns, delta=1000)

    def test_custom_start_and_end_time_with_datetime(self):
        """Test that datetime objects are correctly converted to span timestamps."""
        custom_start = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        custom_end = datetime(2023, 11, 14, 22, 13, 25, tzinfo=UTC)  # 5 seconds later

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start,
            end_time=custom_end,
        )
        scope.dispose()

        span = self._get_finished_span()

        expected_start_ns = int(custom_start.timestamp() * 1_000_000_000)
        expected_end_ns = int(custom_end.timestamp() * 1_000_000_000)

        span_start_ns = span.start_time
        span_end_ns = span.end_time

        self.assertAlmostEqual(span_start_ns, expected_start_ns, delta=1000)
        self.assertAlmostEqual(span_end_ns, expected_end_ns, delta=1000)

    def test_custom_start_and_end_time_with_float_seconds(self):
        """Test that float seconds are correctly converted to span timestamps."""
        # Float seconds since epoch
        custom_start_sec = 1700000000.0  # 2023-11-14T22:13:20Z
        custom_end_sec = 1700000005.5  # 5.5 seconds later

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start_sec,
            end_time=custom_end_sec,
        )
        scope.dispose()

        span = self._get_finished_span()

        expected_start_ns = int(custom_start_sec * 1_000_000_000)
        expected_end_ns = int(custom_end_sec * 1_000_000_000)

        span_start_ns = span.start_time
        span_end_ns = span.end_time

        self.assertAlmostEqual(span_start_ns, expected_start_ns, delta=1000)
        self.assertAlmostEqual(span_end_ns, expected_end_ns, delta=1000)

    def test_custom_start_and_end_time_with_hrtime_tuple(self):
        """Test that HrTime tuples (seconds, nanoseconds) are correctly handled."""
        # HrTime: (seconds, nanoseconds)
        custom_start: tuple[int, int] = (1700000000, 0)  # 2023-11-14T22:13:20Z
        custom_end: tuple[int, int] = (1700000005, 500000000)  # 5.5 seconds later

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start,
            end_time=custom_end,
        )
        scope.dispose()

        span = self._get_finished_span()

        expected_start_ns = custom_start[0] * 1_000_000_000 + custom_start[1]
        expected_end_ns = custom_end[0] * 1_000_000_000 + custom_end[1]

        span_start_ns = span.start_time
        span_end_ns = span.end_time

        self.assertAlmostEqual(span_start_ns, expected_start_ns, delta=1000)
        self.assertAlmostEqual(span_end_ns, expected_end_ns, delta=1000)

    def test_set_end_time_overrides_end_time(self):
        """Test that set_end_time overrides the end time when called before dispose."""
        custom_start_ns = 1700000040000000000
        initial_end_ns = 1700000045000000000  # 5 seconds after start
        later_end_ns = 1700000048000000000  # 8 seconds after start

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start_ns,
            end_time=initial_end_ns,
        )
        # Override the end time
        scope.set_end_time(later_end_ns)
        scope.dispose()

        span = self._get_finished_span()

        span_end_ns = span.end_time
        self.assertAlmostEqual(span_end_ns, later_end_ns, delta=1000)

    def test_wall_clock_time_used_when_no_custom_times(self):
        """Test that wall-clock time is used when no custom times are provided."""
        import time

        before = time.time_ns()
        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
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
        custom_start_ns = 1700000000000000000

        scope = ExecuteToolScope.start(
            self.tool_details,
            self.agent_details,
            self.tenant_details,
            start_time=custom_start_ns,
        )
        scope.dispose()

        span = self._get_finished_span()

        span_start_ns = span.start_time

        # Start time should match what we provided
        self.assertAlmostEqual(span_start_ns, custom_start_ns, delta=1000)

        # End time should be close to current time (not custom)
        span_end_ns = span.end_time
        self.assertGreater(span_end_ns, span_start_ns)


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

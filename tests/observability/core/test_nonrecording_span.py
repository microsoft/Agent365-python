# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests that observability code handles NonRecordingSpan gracefully.

When the TracerProvider has no valid exporter (e.g. token resolver returns
None on the first turn), it produces NonRecordingSpan instances. These only
expose get_span_context() — the .context attribute does not exist. The code
must use get_span_context() everywhere to avoid AttributeError crashes.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from microsoft_agents_a365.observability.core.exporters.enriched_span import (
    EnrichedReadableSpan,
)
from microsoft_agents_a365.observability.core.opentelemetry_scope import (
    OpenTelemetryScope,
)
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags


def _make_non_recording_span(trace_id: int = 0, span_id: int = 0) -> NonRecordingSpan:
    """Create a NonRecordingSpan with the given trace/span IDs."""
    return NonRecordingSpan(
        SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
    )


class TestOpenTelemetryScopeNonRecordingSpan(unittest.TestCase):
    """Verify OpenTelemetryScope works when the tracer returns a NonRecordingSpan."""

    @patch.dict(os.environ, {"ENABLE_OBSERVABILITY": "true"})
    @patch.object(OpenTelemetryScope, "_get_tracer")
    def test_init_with_non_recording_span(self, mock_get_tracer: MagicMock) -> None:
        """__init__ must not crash when tracer.start_span returns NonRecordingSpan."""
        mock_tracer = MagicMock()
        nr_span = _make_non_recording_span(trace_id=0xABCD, span_id=0x1234)
        mock_tracer.start_span.return_value = nr_span
        mock_get_tracer.return_value = mock_tracer

        # Should not raise AttributeError
        scope = OpenTelemetryScope(
            operation_name="invoke_agent",
            activity_name="test_activity",
        )

        self.assertIs(scope._span, nr_span)

    @patch.dict(os.environ, {"ENABLE_OBSERVABILITY": "true"})
    @patch.object(OpenTelemetryScope, "_get_tracer")
    def test_end_with_non_recording_span(self, mock_get_tracer: MagicMock) -> None:
        """_end() must not crash when the span is a NonRecordingSpan."""
        mock_tracer = MagicMock()
        nr_span = _make_non_recording_span(trace_id=0xABCD, span_id=0x1234)
        mock_tracer.start_span.return_value = nr_span
        mock_get_tracer.return_value = mock_tracer

        scope = OpenTelemetryScope(
            operation_name="invoke_agent",
            activity_name="test_activity",
        )

        # Should not raise AttributeError
        scope._end()

    @patch.dict(os.environ, {"ENABLE_OBSERVABILITY": "true"})
    @patch.object(OpenTelemetryScope, "_get_tracer")
    def test_dispose_with_non_recording_span(self, mock_get_tracer: MagicMock) -> None:
        """Full dispose lifecycle must not crash with NonRecordingSpan."""
        mock_tracer = MagicMock()
        nr_span = _make_non_recording_span(trace_id=0xABCD, span_id=0x1234)
        mock_tracer.start_span.return_value = nr_span
        mock_get_tracer.return_value = mock_tracer

        scope = OpenTelemetryScope(
            operation_name="invoke_agent",
            activity_name="test_activity",
        )

        # Context manager exit should not raise
        scope.__exit__(None, None, None)


class TestEnrichedReadableSpanNonRecordingSpan(unittest.TestCase):
    """Verify EnrichedReadableSpan delegates context via get_span_context()."""

    def test_context_property_uses_get_span_context(self) -> None:
        """EnrichedReadableSpan.context must call get_span_context(), not .context."""
        mock_span = MagicMock()
        expected_ctx = SpanContext(
            trace_id=0xFF,
            span_id=0xAA,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
        mock_span.get_span_context.return_value = expected_ctx
        # Ensure .context attribute is NOT used
        del mock_span.context

        enriched = EnrichedReadableSpan(mock_span, extra_attributes={"key": "val"})

        result = enriched.context
        self.assertIs(result, expected_ctx)
        mock_span.get_span_context.assert_called_once()

    def test_to_json_with_non_recording_span_context(self) -> None:
        """to_json() must not crash when wrapped span uses get_span_context()."""
        mock_span = MagicMock()
        mock_span.name = "test"
        mock_span.get_span_context.return_value = SpanContext(
            trace_id=0x1234,
            span_id=0x5678,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
        del mock_span.context
        mock_span.attributes = {"key": "value"}
        mock_span.kind = "INTERNAL"
        mock_span.parent = None
        mock_span.start_time = 1000000000
        mock_span.end_time = 2000000000
        mock_span.status = None
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = None

        enriched = EnrichedReadableSpan(mock_span, extra_attributes={})

        # Should not raise
        json_str = enriched.to_json()
        self.assertIn("test", json_str)
        self.assertIn("0x00000000000000000000000000001234", json_str)


class TestAgent365ExporterMapSpanGetSpanContext(unittest.TestCase):
    """Verify _map_span uses get_span_context() instead of .context."""

    @patch.dict(os.environ, {}, clear=True)
    def test_map_span_calls_get_span_context(self) -> None:
        """_map_span must use get_span_context(), not .context attribute."""
        from microsoft_agents_a365.observability.core.exporters.agent365_exporter import (
            _Agent365Exporter,
        )

        exporter = _Agent365Exporter(token_resolver=lambda a, t: "token")

        span = MagicMock()
        span.name = "test_span"
        span.attributes = {"gen_ai.operation.name": "invoke_agent"}

        expected_ctx = SpanContext(
            trace_id=0xABCD,
            span_id=0x1234,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
        span.get_span_context.return_value = expected_ctx
        # Remove .context so it would fail if accessed
        del span.context

        span.parent = None
        span.kind = MagicMock()
        span.start_time = 1000000000
        span.end_time = 2000000000
        span.status = MagicMock()
        span.status.status_code = MagicMock()
        span.status.description = ""
        span.events = []
        span.links = []
        span.instrumentation_scope = MagicMock()
        span.instrumentation_scope.name = "test"
        span.instrumentation_scope.version = "1.0"

        # Should not raise AttributeError
        mapped = exporter._map_span(span)

        span.get_span_context.assert_called_once()
        self.assertIn("traceId", mapped)
        self.assertIn("spanId", mapped)
        exporter.shutdown()


if __name__ == "__main__":
    unittest.main()

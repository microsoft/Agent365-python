# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for EnrichedReadableSpan."""

import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.exporters.enriched_span import EnrichedReadableSpan


class TestEnrichedReadableSpan(unittest.TestCase):
    """Test suite for EnrichedReadableSpan."""

    def test_attributes_merges_original_and_extra(self):
        """Test that attributes property merges original span attributes with extra attributes."""
        # Create mock span with original attributes
        mock_span = Mock()
        mock_span.attributes = {"original_key": "original_value", "shared_key": "original"}

        # Create enriched span with extra attributes
        extra_attributes = {"extra_key": "extra_value", "shared_key": "overwritten"}
        enriched_span = EnrichedReadableSpan(mock_span, extra_attributes)

        # Verify merged attributes
        attributes = enriched_span.attributes
        self.assertEqual(attributes["original_key"], "original_value")
        self.assertEqual(attributes["extra_key"], "extra_value")
        self.assertEqual(attributes["shared_key"], "overwritten")  # Extra should overwrite original

    def test_delegates_all_properties_to_wrapped_span(self):
        """Test that all span properties are delegated to the wrapped span."""
        # Create mock span with all properties
        mock_span = Mock()
        mock_span.name = "test-span"
        mock_span.context = Mock(trace_id=123, span_id=456)
        mock_span.parent = Mock(span_id=789)
        mock_span.start_time = 1000000000
        mock_span.end_time = 2000000000
        mock_span.status = Mock(status_code="OK", description=None)
        mock_span.kind = "INTERNAL"
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = Mock(attributes={"service.name": "test"})
        mock_span.instrumentation_scope = Mock(name="test-scope")
        mock_span.attributes = {}

        enriched_span = EnrichedReadableSpan(mock_span, {})

        # Verify all properties delegate correctly
        self.assertEqual(enriched_span.name, "test-span")
        self.assertEqual(enriched_span.context, mock_span.context)
        self.assertEqual(enriched_span.parent, mock_span.parent)
        self.assertEqual(enriched_span.start_time, 1000000000)
        self.assertEqual(enriched_span.end_time, 2000000000)
        self.assertEqual(enriched_span.status, mock_span.status)
        self.assertEqual(enriched_span.kind, "INTERNAL")
        self.assertEqual(enriched_span.events, [])
        self.assertEqual(enriched_span.links, [])
        self.assertEqual(enriched_span.resource, mock_span.resource)
        self.assertEqual(enriched_span.instrumentation_scope, mock_span.instrumentation_scope)


if __name__ == "__main__":
    unittest.main()

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for enriching_span_processor module."""

import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
    _span_enrichers,
    register_span_enricher,
    unregister_span_enricher,
)


class TestSpanEnricherRegistry(unittest.TestCase):
    """Test suite for span enricher registration functions."""

    def setUp(self):
        """Clear enrichers before each test."""
        _span_enrichers.clear()

    def tearDown(self):
        """Clear enrichers after each test."""
        _span_enrichers.clear()

    def test_register_and_unregister_enricher(self):
        """Test that enrichers can be registered and unregistered."""

        # Define a simple enricher
        def my_enricher(span):
            return span

        # Register
        register_span_enricher(my_enricher)
        self.assertIn(my_enricher, _span_enrichers)
        self.assertEqual(len(_span_enrichers), 1)

        # Duplicate registration should not add again
        register_span_enricher(my_enricher)
        self.assertEqual(len(_span_enrichers), 1)

        # Unregister
        unregister_span_enricher(my_enricher)
        self.assertNotIn(my_enricher, _span_enrichers)
        self.assertEqual(len(_span_enrichers), 0)

    def test_unregister_nonexistent_enricher_does_not_raise(self):
        """Test that unregistering a non-existent enricher doesn't raise an error."""

        def my_enricher(span):
            return span

        # Should not raise
        unregister_span_enricher(my_enricher)
        self.assertEqual(len(_span_enrichers), 0)


class TestEnrichingBatchSpanProcessor(unittest.TestCase):
    """Test suite for _EnrichingBatchSpanProcessor."""

    def setUp(self):
        """Clear enrichers before each test."""
        _span_enrichers.clear()

    def tearDown(self):
        """Clear enrichers after each test."""
        _span_enrichers.clear()

    def test_on_end_applies_enrichers_to_span(self):
        """Test that on_end applies all registered enrichers to the span."""
        # Create processor with a mock exporter
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter)

        # Register an enricher that tracks what it receives and returns
        received_spans = []

        def enricher(span):
            received_spans.append(span)
            # Return a mock enriched span
            enriched = Mock(name="enriched_span")
            enriched.context = span.context
            return enriched

        register_span_enricher(enricher)

        # Create a mock span
        original_span = Mock(name="original_span")
        original_span.context = Mock()
        original_span.context.trace_id = 123
        original_span.context.span_id = 456

        # Call on_end
        processor.on_end(original_span)

        # Verify enricher was called with the original span
        self.assertEqual(len(received_spans), 1)
        self.assertEqual(received_spans[0], original_span)

        # Cleanup
        processor.shutdown()

    def test_on_end_continues_if_enricher_raises_exception(self):
        """Test that on_end continues processing even if an enricher raises an exception."""
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter)

        # Track which enrichers were called
        called_enrichers = []

        def failing_enricher(span):
            called_enrichers.append("failing")
            raise ValueError("Enricher failed!")

        def succeeding_enricher(span):
            called_enrichers.append("succeeding")
            return span

        register_span_enricher(failing_enricher)
        register_span_enricher(succeeding_enricher)

        # Create a mock span
        original_span = Mock(name="original_span")
        original_span.context = Mock()
        original_span.context.trace_id = 123
        original_span.context.span_id = 456

        # Should not raise despite failing enricher
        processor.on_end(original_span)

        # Verify both enrichers were called (failing one didn't stop the chain)
        self.assertIn("failing", called_enrichers)
        self.assertIn("succeeding", called_enrichers)

        # Cleanup
        processor.shutdown()


if __name__ == "__main__":
    unittest.main()

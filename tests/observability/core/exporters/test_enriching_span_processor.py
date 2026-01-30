# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for enriching_span_processor module."""

import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
    get_span_enricher,
    register_span_enricher,
    unregister_span_enricher,
)


class TestSpanEnricherRegistry(unittest.TestCase):
    """Test suite for span enricher registration functions."""

    def setUp(self):
        """Ensure clean state before each test."""
        unregister_span_enricher()

    def tearDown(self):
        """Clean up after each test."""
        unregister_span_enricher()

    def test_register_and_unregister_enricher(self):
        """Test that enricher can be registered and unregistered."""

        def my_enricher(span):
            return span

        # Initially no enricher
        self.assertIsNone(get_span_enricher())

        # Register
        register_span_enricher(my_enricher)
        self.assertEqual(get_span_enricher(), my_enricher)

        # Unregister
        unregister_span_enricher()
        self.assertIsNone(get_span_enricher())

    def test_register_second_enricher_raises_error(self):
        """Test that registering a second enricher raises RuntimeError."""

        def enricher_one(span):
            return span

        def enricher_two(span):
            return span

        register_span_enricher(enricher_one)

        with self.assertRaises(RuntimeError) as context:
            register_span_enricher(enricher_two)

        self.assertIn("already registered", str(context.exception))

    def test_unregister_when_none_registered_is_safe(self):
        """Test that unregistering when no enricher is registered doesn't raise."""
        # Should not raise
        unregister_span_enricher()
        self.assertIsNone(get_span_enricher())


class TestEnrichingBatchSpanProcessor(unittest.TestCase):
    """Test suite for _EnrichingBatchSpanProcessor."""

    def setUp(self):
        """Ensure clean state before each test."""
        unregister_span_enricher()

    def tearDown(self):
        """Clean up after each test."""
        unregister_span_enricher()

    def test_on_end_applies_enricher_to_span(self):
        """Test that on_end applies the registered enricher to the span."""
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
        """Test that on_end continues processing even if enricher raises an exception."""
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter)

        def failing_enricher(span):
            raise ValueError("Enricher failed!")

        register_span_enricher(failing_enricher)

        # Create a mock span
        original_span = Mock(name="original_span")
        original_span.context = Mock()
        original_span.context.trace_id = 123
        original_span.context.span_id = 456

        # Should not raise despite failing enricher
        processor.on_end(original_span)

        # Cleanup
        processor.shutdown()

    def test_on_end_works_without_enricher(self):
        """Test that on_end works when no enricher is registered."""
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter)

        # Create a mock span (no enricher registered)
        original_span = Mock(name="original_span")
        original_span.context = Mock()
        original_span.context.trace_id = 123
        original_span.context.span_id = 456

        # Should not raise
        processor.on_end(original_span)

        # Cleanup
        processor.shutdown()


if __name__ == "__main__":
    unittest.main()

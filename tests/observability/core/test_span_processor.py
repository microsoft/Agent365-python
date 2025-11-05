# Copyright (c) Microsoft. All rights reserved.


import unittest
from unittest.mock import MagicMock

from opentelemetry import context

from microsoft_agents_a365.observability.core.trace_processor.span_processor import SpanProcessor


class TestSpanProcessor(unittest.TestCase):
    def setUp(self):
        # Clear any existing context/baggage before each test
        context.attach({})

        self.processor = SpanProcessor()
        self.mock_span = MagicMock()
        self.mock_context = None  # Root span

    def test_on_start_with_no_baggage(self):
        # Call on_start with no baggage, should not set agent_id since there's none
        self.processor.on_start(self.mock_span, self.mock_context)
        # Should not call set_attribute since there's no agent_id in baggage or config
        self.mock_span.set_attribute.assert_not_called()
        print("✅ Span on_start(Span, Parent) with no baggage testing passed!")

    def test_on_end_calls_super(self):
        try:
            self.processor.on_end(self.mock_span)
            print("✅ Span on_end(ReadableSpan) testing passed!")
        except Exception as e:
            self.fail(f"on_end raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()

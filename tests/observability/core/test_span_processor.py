# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import MagicMock

from microsoft_agents_a365.observability.core.constants import OPERATION_SOURCE_KEY
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
from microsoft_agents_a365.observability.core.models.operation_source import OperationSource
from microsoft_agents_a365.observability.core.trace_processor.span_processor import SpanProcessor
from opentelemetry import context


class TestSpanProcessor(unittest.TestCase):
    def setUp(self):
        # Clear any existing context/baggage before each test
        context.attach({})

        self.processor = SpanProcessor()
        self.mock_span = MagicMock()
        self.mock_context = None  # Root span

    def test_operation_source_defaults_to_sdk(self):
        """Test that operation source is set to SDK by default when not in baggage."""
        # Mock span with no existing attributes
        self.mock_span.attributes = {}

        # Call on_start with no baggage
        self.processor.on_start(self.mock_span, self.mock_context)

        # Verify SDK was set as default operation source
        self.mock_span.set_attribute.assert_called_with(
            OPERATION_SOURCE_KEY, OperationSource.SDK.value
        )

    def test_operation_source_honors_baggage_value(self):
        """Test that operation source from baggage is used when available."""
        # Mock span with no existing attributes
        self.mock_span.attributes = {}

        # Set operation source in baggage using BaggageBuilder
        with BaggageBuilder().operation_source(OperationSource.GATEWAY).build():
            # Call on_start - should use baggage value
            self.processor.on_start(self.mock_span, context.get_current())

        # Verify GATEWAY was used from baggage
        self.mock_span.set_attribute.assert_called_with(
            OPERATION_SOURCE_KEY, OperationSource.GATEWAY.value
        )

    def test_on_end_calls_super(self):
        try:
            self.processor.on_end(self.mock_span)
        except Exception as e:
            self.fail(f"on_end raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import MagicMock

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_VERSION_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
from microsoft_agents_a365.observability.core.trace_processor.span_processor import SpanProcessor
from opentelemetry import context


class TestSpanProcessor(unittest.TestCase):
    def setUp(self):
        # Clear any existing context/baggage before each test
        context.attach({})

        self.processor = SpanProcessor()
        self.mock_span = MagicMock()
        self.mock_context = None  # Root span

    def test_baggage_propagates_to_span(self):
        """Test that baggage values are propagated to span attributes."""
        # Mock span with no existing attributes
        self.mock_span.attributes = {}

        # Set values in baggage using BaggageBuilder
        with BaggageBuilder().tenant_id("test-tenant").agent_id("test-agent").build():
            # Call on_start - should propagate baggage values
            self.processor.on_start(self.mock_span, context.get_current())

        # Verify baggage values were set on the span
        calls = self.mock_span.set_attribute.call_args_list
        call_dict = {call[0][0]: call[0][1] for call in calls}
        self.assertEqual(call_dict.get(TENANT_ID_KEY), "test-tenant")
        self.assertEqual(call_dict.get(GEN_AI_AGENT_ID_KEY), "test-agent")

    def test_on_end_calls_super(self):
        try:
            self.processor.on_end(self.mock_span)
        except Exception as e:
            self.fail(f"on_end raised an exception: {e}")

    def test_agent_version_baggage_propagates_to_span(self):
        """Test that agent version baggage is propagated to span attributes."""
        self.mock_span.attributes = {}

        with (
            BaggageBuilder()
            .tenant_id("test-tenant")
            .agent_id("test-agent")
            .agent_version("3.0.0")
            .build()
        ):
            self.processor.on_start(self.mock_span, context.get_current())

        calls = self.mock_span.set_attribute.call_args_list
        call_dict = {call[0][0]: call[0][1] for call in calls}
        self.assertEqual(call_dict.get(GEN_AI_AGENT_VERSION_KEY), "3.0.0")
        self.assertEqual(call_dict.get(TENANT_ID_KEY), "test-tenant")
        self.assertEqual(call_dict.get(GEN_AI_AGENT_ID_KEY), "test-agent")


if __name__ == "__main__":
    unittest.main()

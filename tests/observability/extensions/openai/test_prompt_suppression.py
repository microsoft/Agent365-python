# Copyright (c) Microsoft. All rights reserved.

import unittest
from datetime import datetime
from unittest.mock import Mock

from agents.tracing import Span
from agents.tracing.span_data import AgentSpanData, GenerationSpanData, ResponseSpanData
from microsoft_agents_a365.observability.core import configure, get_tracer
from microsoft_agents_a365.observability.core.constants import GEN_AI_INPUT_MESSAGES_KEY
from microsoft_agents_a365.observability.extensions.openai.trace_processor import (
    OpenAIAgentsTraceProcessor,
)
from openai.types.responses import Response


class TestPromptSuppression(unittest.TestCase):
    """Unit tests for prompt suppression functionality in OpenAIAgentsTraceProcessor."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        configure(
            service_name="test-service-prompt-suppression",
            service_namespace="test-namespace-prompt-suppression",
        )

    def setUp(self):
        """Set up each test with a fresh processor and mock tracer."""
        self.tracer = get_tracer()
        self.mock_otel_span = Mock()
        self.mock_otel_span.attributes = {}
        self.mock_otel_span.get_span_context.return_value = Mock(
            trace_id="test-trace-id", span_id="test-span-id"
        )
        
        # Track attributes set on the span
        def set_attribute_side_effect(key, value):
            self.mock_otel_span.attributes[key] = value
        
        self.mock_otel_span.set_attribute = Mock(side_effect=set_attribute_side_effect)
        self.mock_otel_span.update_name = Mock()
        self.mock_otel_span.set_status = Mock()
        self.mock_otel_span.end = Mock()

        # Mock the tracer's start_span method
        self.original_start_span = self.tracer.start_span
        self.tracer.start_span = Mock(return_value=self.mock_otel_span)

    def tearDown(self):
        """Clean up after each test."""
        self.tracer.start_span = self.original_start_span

    def test_does_not_record_input_messages_when_suppression_enabled_in_agent_scope(self):
        """Test that input messages are not recorded when suppression is enabled and in agent scope."""
        processor = OpenAIAgentsTraceProcessor(self.tracer, suppress_invoke_agent_input=True)

        trace_id = "trace-suppress"
        now = datetime.now().isoformat()

        # Start an agent span to create InvokeAgent scope
        agent_span = Mock(spec=Span)
        agent_span.span_id = "agent-span"
        agent_span.trace_id = trace_id
        agent_span.parent_id = None
        agent_span.started_at = now
        agent_span.ended_at = None
        agent_span.span_data = AgentSpanData(name="TestAgent")

        processor.on_span_start(agent_span)

        # Now create a generation span with input (proper format - list of message dicts)
        gen_span = Mock(spec=Span)
        gen_span.span_id = "gen-span"
        gen_span.trace_id = trace_id
        gen_span.parent_id = "agent-span"
        gen_span.started_at = now
        gen_span.ended_at = now
        gen_span.span_data = GenerationSpanData(
            model="gpt-4",
            input=[{"role": "user", "content": "Hello prompt"}]
        )

        processor.on_span_start(gen_span)
        processor.on_span_end(gen_span)

        # Verify that set_attribute was called but NOT with GEN_AI_INPUT_MESSAGES_KEY
        attribute_keys = [call[0][0] for call in self.mock_otel_span.set_attribute.call_args_list]
        self.assertNotIn(
            GEN_AI_INPUT_MESSAGES_KEY,
            attribute_keys,
            "GEN_AI_INPUT_MESSAGES_KEY should not be set when suppression is enabled",
        )

    def test_records_input_messages_when_suppression_disabled(self):
        """Test that input messages are recorded when suppression is disabled (default)."""
        processor = OpenAIAgentsTraceProcessor(self.tracer, suppress_invoke_agent_input=False)

        trace_id = "trace-allow"
        now = datetime.now().isoformat()

        # Start an agent span
        agent_span = Mock(spec=Span)
        agent_span.span_id = "agent-span-2"
        agent_span.trace_id = trace_id
        agent_span.parent_id = None
        agent_span.started_at = now
        agent_span.ended_at = None
        agent_span.span_data = AgentSpanData(name="TestAgent")

        processor.on_span_start(agent_span)

        # Create a generation span with input (proper format - list of message dicts)
        gen_span = Mock(spec=Span)
        gen_span.span_id = "gen-span-2"
        gen_span.trace_id = trace_id
        gen_span.parent_id = "agent-span-2"
        gen_span.started_at = now
        gen_span.ended_at = now
        gen_span.span_data = GenerationSpanData(
            model="gpt-4",
            input=[{"role": "user", "content": "Hello prompt"}]
        )

        processor.on_span_start(gen_span)
        processor.on_span_end(gen_span)

        # Verify that set_attribute was called with GEN_AI_INPUT_MESSAGES_KEY
        attribute_keys = [call[0][0] for call in self.mock_otel_span.set_attribute.call_args_list]
        self.assertIn(
            GEN_AI_INPUT_MESSAGES_KEY,
            attribute_keys,
            "GEN_AI_INPUT_MESSAGES_KEY should be set when suppression is disabled",
        )

    def test_suppresses_input_on_response_spans_when_enabled(self):
        """Test that input is suppressed on response spans when suppression is enabled."""
        processor = OpenAIAgentsTraceProcessor(self.tracer, suppress_invoke_agent_input=True)

        trace_id = "trace-resp"
        now = datetime.now().isoformat()

        # Start an agent span
        agent_span = Mock(spec=Span)
        agent_span.span_id = "agent-span-3"
        agent_span.trace_id = trace_id
        agent_span.parent_id = None
        agent_span.started_at = now
        agent_span.ended_at = None
        agent_span.span_data = AgentSpanData(name="TestAgent")

        processor.on_span_start(agent_span)

        # Create a response span with input
        resp_span = Mock(spec=Span)
        resp_span.span_id = "resp-span"
        resp_span.trace_id = trace_id
        resp_span.parent_id = "agent-span-3"
        resp_span.started_at = now
        resp_span.ended_at = now

        # Create mock response data with all required attributes
        mock_response = Mock(spec=Response)
        mock_response.model_dump_json.return_value = '{"output": "test"}'
        mock_response.tools = None
        mock_response.usage = None
        mock_response.output = None
        mock_response.instructions = None
        mock_response.model = "gpt-4"
        mock_response.model_dump.return_value = {}

        resp_span.span_data = Mock(spec=ResponseSpanData)
        resp_span.span_data.response = mock_response
        resp_span.span_data.input = "Prompt text"

        processor.on_span_start(resp_span)
        processor.on_span_end(resp_span)

        # Verify that set_attribute was called but NOT with GEN_AI_INPUT_MESSAGES_KEY for input
        attribute_keys = [call[0][0] for call in self.mock_otel_span.set_attribute.call_args_list]
        self.assertNotIn(
            GEN_AI_INPUT_MESSAGES_KEY,
            attribute_keys,
            "GEN_AI_INPUT_MESSAGES_KEY should not be set for response span when suppression is enabled",
        )

    def test_records_input_outside_agent_scope_even_when_suppression_enabled(self):
        """Test that input messages are recorded outside agent scope even when suppression is enabled."""
        processor = OpenAIAgentsTraceProcessor(self.tracer, suppress_invoke_agent_input=True)

        trace_id = "trace-outside"
        now = datetime.now().isoformat()

        # Create a generation span WITHOUT an agent span (outside InvokeAgent scope)
        gen_span = Mock(spec=Span)
        gen_span.span_id = "gen-span-outside"
        gen_span.trace_id = trace_id
        gen_span.parent_id = None
        gen_span.started_at = now
        gen_span.ended_at = now
        gen_span.span_data = GenerationSpanData(
            model="gpt-4",
            input=[{"role": "user", "content": "Hello prompt"}]
        )

        processor.on_span_start(gen_span)
        processor.on_span_end(gen_span)

        # Verify that set_attribute WAS called with GEN_AI_INPUT_MESSAGES_KEY
        # because we're not in an InvokeAgent scope
        attribute_keys = [call[0][0] for call in self.mock_otel_span.set_attribute.call_args_list]
        self.assertIn(
            GEN_AI_INPUT_MESSAGES_KEY,
            attribute_keys,
            "GEN_AI_INPUT_MESSAGES_KEY should be set when outside InvokeAgent scope",
        )

    def test_default_suppression_is_false(self):
        """Test that the default value for suppress_invoke_agent_input is False."""
        processor = OpenAIAgentsTraceProcessor(self.tracer)

        self.assertFalse(
            processor._suppress_invoke_agent_input,
            "Default value for suppress_invoke_agent_input should be False",
        )

    def test_agent_span_tracking_cleanup(self):
        """Test that agent span tracking is properly cleaned up when spans end."""
        processor = OpenAIAgentsTraceProcessor(self.tracer, suppress_invoke_agent_input=True)

        trace_id = "trace-cleanup"
        now = datetime.now().isoformat()

        # Start an agent span
        agent_span = Mock(spec=Span)
        agent_span.span_id = "agent-span-cleanup"
        agent_span.trace_id = trace_id
        agent_span.parent_id = None
        agent_span.started_at = now
        agent_span.ended_at = now
        agent_span.span_data = AgentSpanData(name="TestAgent")

        processor.on_span_start(agent_span)

        # Verify the span is tracked
        self.assertIn(trace_id, processor._active_agent_spans)
        self.assertIn(agent_span.span_id, processor._active_agent_spans[trace_id])

        # End the agent span
        processor.on_span_end(agent_span)

        # Verify the tracking is cleaned up
        self.assertNotIn(trace_id, processor._active_agent_spans)


def run_tests():
    """Run all prompt suppression tests."""
    print("🧪 Running prompt suppression tests...")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPromptSuppression)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("🏁 Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("🎉 All tests passed!")
        return True
    else:
        print("🔧 Some tests failed. Check output above.")
        return False


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

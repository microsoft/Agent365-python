# Copyright (c) Microsoft. All rights reserved.

import unittest

from microsoft_agents_a365.observability.core import configure, get_tracer
from microsoft_agents_a365.observability.extensions.openai.trace_processor import (
    OpenAIAgentsTraceProcessor,
)


class TestPromptSuppressionConfiguration(unittest.TestCase):
    """Unit tests for prompt suppression configuration in OpenAIAgentsTraceProcessor."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        configure(
            service_name="test-service-prompt-suppression",
            service_namespace="test-namespace-prompt-suppression",
        )

    def test_default_suppression_is_false(self):
        """Test that the default value for suppress_invoke_agent_input is False."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer)

        self.assertFalse(
            processor._suppress_invoke_agent_input,
            "Default value for suppress_invoke_agent_input should be False",
        )

    def test_can_enable_suppression(self):
        """Test that suppression can be enabled via constructor."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer, suppress_invoke_agent_input=True)

        self.assertTrue(
            processor._suppress_invoke_agent_input,
            "suppress_invoke_agent_input should be True when explicitly set",
        )

    def test_can_disable_suppression(self):
        """Test that suppression can be explicitly disabled via constructor."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer, suppress_invoke_agent_input=False)

        self.assertFalse(
            processor._suppress_invoke_agent_input,
            "suppress_invoke_agent_input should be False when explicitly set",
        )

    def test_has_active_agent_spans_tracking(self):
        """Test that the processor has the required tracking data structure."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer, suppress_invoke_agent_input=True)

        self.assertTrue(
            hasattr(processor, "_active_agent_spans"),
            "Processor should have _active_agent_spans attribute",
        )
        self.assertIsInstance(
            processor._active_agent_spans,
            dict,
            "_active_agent_spans should be a dictionary",
        )

    def test_has_is_in_invoke_agent_scope_method(self):
        """Test that the processor has the helper method for scope detection."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer, suppress_invoke_agent_input=True)

        self.assertTrue(
            hasattr(processor, "_is_in_invoke_agent_scope"),
            "Processor should have _is_in_invoke_agent_scope method",
        )
        self.assertTrue(
            callable(processor._is_in_invoke_agent_scope),
            "_is_in_invoke_agent_scope should be callable",
        )

    def test_is_in_invoke_agent_scope_returns_false_for_empty_trace(self):
        """Test that _is_in_invoke_agent_scope returns False for unknown trace."""
        tracer = get_tracer()
        processor = OpenAIAgentsTraceProcessor(tracer, suppress_invoke_agent_input=True)

        result = processor._is_in_invoke_agent_scope("unknown-trace-id")

        self.assertFalse(
            result,
            "_is_in_invoke_agent_scope should return False for traces with no active agent spans",
        )


def run_tests():
    """Run all prompt suppression configuration tests."""
    print("🧪 Running prompt suppression configuration tests...")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPromptSuppressionConfiguration)

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

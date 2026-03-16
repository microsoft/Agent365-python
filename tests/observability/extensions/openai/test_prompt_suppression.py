# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
)


class TestPromptSuppressionConfiguration(unittest.TestCase):
    """Unit tests for prompt suppression configuration in the core SDK."""

    def test_processor_default_suppression_is_false(self):
        """Test that the default value for suppress_invoke_agent_input is False in processor."""
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter)

        self.assertFalse(
            processor._suppress_invoke_agent_input,
            "Default value for suppress_invoke_agent_input should be False",
        )
        processor.shutdown()

    def test_processor_can_enable_suppression(self):
        """Test that suppression can be enabled via processor constructor."""
        mock_exporter = Mock()
        processor = _EnrichingBatchSpanProcessor(mock_exporter, suppress_invoke_agent_input=True)

        self.assertTrue(
            processor._suppress_invoke_agent_input,
            "suppress_invoke_agent_input should be True when explicitly set",
        )
        processor.shutdown()


def run_tests():
    """Run all prompt suppression configuration tests."""
    print("Running prompt suppression configuration tests...")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPromptSuppressionConfiguration)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("All tests passed!")
        return True
    else:
        print("Some tests failed. Check output above.")
        return False


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

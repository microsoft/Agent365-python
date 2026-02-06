# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest

from microsoft_agents_a365.observability.core.exporters.agent365_exporter import _Agent365Exporter


class TestPromptSuppressionConfiguration(unittest.TestCase):
    """Unit tests for prompt suppression configuration in the core SDK."""

    def test_exporter_default_suppression_is_false(self):
        """Test that the default value for suppress_invoke_agent_input is False in exporter."""
        exporter = _Agent365Exporter(token_resolver=lambda x, y: "test")

        self.assertFalse(
            exporter._suppress_invoke_agent_input,
            "Default value for suppress_invoke_agent_input should be False",
        )

    def test_exporter_can_enable_suppression(self):
        """Test that suppression can be enabled via exporter constructor."""
        exporter = _Agent365Exporter(
            token_resolver=lambda x, y: "test", suppress_invoke_agent_input=True
        )

        self.assertTrue(
            exporter._suppress_invoke_agent_input,
            "suppress_invoke_agent_input should be True when explicitly set",
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

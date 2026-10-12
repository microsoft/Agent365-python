# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_RESPONSE_MODEL_KEY,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS_KEY,
)
from microsoft_agents_a365.observability.extensions.openai import OpenAIAgentsTraceInstrumentor
from microsoft_agents_a365.observability.extensions.openai.utils import (
    get_attributes_from_response,
    get_attributes_from_usage,
)


class TestOpenAIModelObservationAttributes(unittest.TestCase):
    """Unit tests for model observation attribute mapping."""

    def test_response_model_uses_response_attribute(self):
        """Test that the served model is emitted as the response model."""
        response = MagicMock()
        response.tools = []
        response.usage = None
        response.output = []
        response.instructions = None
        response.model = "gpt-4.1-2025-04-14"
        response.model_dump.return_value = {}

        attributes = dict(get_attributes_from_response(response))

        self.assertEqual(attributes[GEN_AI_RESPONSE_MODEL_KEY], "gpt-4.1-2025-04-14")

    def test_cached_tokens_use_standard_attribute(self):
        """Test that cached input tokens use the model observation attribute."""
        usage = SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            input_tokens_details=SimpleNamespace(cached_tokens=40),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
        )

        attributes = dict(get_attributes_from_usage(usage))

        self.assertEqual(attributes[GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS_KEY], 40)


class TestOpenAIAgentsTraceInstrumentor(unittest.TestCase):
    """Unit tests for OpenAIAgentsTraceInstrumentor class."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        configure(
            service_name="test-service-openaiAgents",
            service_namespace="test-namespace-openaiAgents",
        )

    def test_instrumentor_initialization(self):
        """Test 1: Verify OpenAIAgentsTraceInstrumentor can be initialized successfully."""
        try:
            # Test basic initialization
            instrumentor = OpenAIAgentsTraceInstrumentor()

            # Verify the object was created
            self.assertIsNotNone(instrumentor)
            self.assertIsInstance(instrumentor, OpenAIAgentsTraceInstrumentor)

            # Check if it has expected attributes/methods
            self.assertTrue(hasattr(instrumentor, "__init__"))

            print("✅ Test 1 passed: OpenAIAgentsTraceInstrumentor initialized successfully")

        except Exception as e:
            self.fail(f"OpenAIAgentsTraceInstrumentor initialization failed: {e}")

    def test_instrumentor_methods_exist(self):
        """Test 2: Verify OpenAIAgentsTraceInstrumentor has expected methods."""
        instrumentor = OpenAIAgentsTraceInstrumentor()

        # Test for common instrumentor methods that might exist
        expected_methods = ["__init__", "_instrument"]

        for method_name in expected_methods:
            with self.subTest(method=method_name):
                self.assertTrue(
                    hasattr(instrumentor, method_name),
                    f"Method '{method_name}' should exist on OpenAIAgentsTraceInstrumentor",
                )

        # Test that the object responds to dir() without error
        methods_and_attrs = dir(instrumentor)
        self.assertIsInstance(methods_and_attrs, list)
        self.assertGreater(len(methods_and_attrs), 0)

        print("✅ Test 2 passed: OpenAIAgentsTraceInstrumentor has expected methods")


class TestAgent365InstrumentorIntegration(unittest.TestCase):
    """Integration tests for the instrumentor with the broader Microsoft Agent 365 system."""

    def setUp(self):
        """Set up each test with a fresh Microsoft Agent 365 configuration."""
        configure(
            service_name="integration-test-service",
            service_namespace="integration-test-namespace",
        )

    def test_instrumentor_with_Agent365_configured(self):
        """Test instrumentor behavior when Microsoft Agent 365 is properly configured."""
        from microsoft_agents_a365.observability.core import get_tracer, is_configured

        # Verify Microsoft Agent 365 is configured
        self.assertTrue(is_configured())

        # Get tracer to ensure it works
        tracer = get_tracer()
        self.assertIsNotNone(tracer)

        # Now create instrumentor
        instrumentor = OpenAIAgentsTraceInstrumentor()
        self.assertIsNotNone(instrumentor)

        print("✅ Integration test passed: Instrumentor works with configured Microsoft Agent 365")


def run_comprehensive_tests():
    """Run all tests with detailed output."""
    print("🧪 Running comprehensive Microsoft Agent 365 OpenAI Agents Instrumentor tests...")
    print("=" * 80)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOpenAIAgentsTraceInstrumentor))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent365InstrumentorIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
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
    # Run comprehensive tests
    success = run_comprehensive_tests()
    exit(0 if success else 1)

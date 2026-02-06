# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.extensions.langchain.tracer_instrumentor import (
    CustomLangChainInstrumentor,
)


class TestInstrumentorLangChain(unittest.TestCase):
    """Unit tests for InstrumentorForLangChain class."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        configure(
            service_name="test-service-langchain",
            service_namespace="test-namespace-langchain",
        )

    def setUp(self):
        """Reset instrumentation state before each test."""
        # Clear the global instrumentation state
        CustomLangChainInstrumentor._instance = None
        if hasattr(CustomLangChainInstrumentor, "_instrumented"):
            CustomLangChainInstrumentor._instrumented = False

    def tearDown(self):
        """Clean up after each test."""
        try:
            instrumentor = getattr(self, "_test_instrumentor", None)
            if instrumentor:
                instrumentor._uninstrument()
        except Exception:
            pass

    def test_instrumentor_initialization_and_Agent365_integration(self):
        """Test 1: Verify InstrumentorForLangChain initializes and integrates with Microsoft Agent 365."""
        from microsoft_agents_a365.observability.core.config import get_tracer, is_configured

        # Verify Microsoft Agent 365 is configured
        self.assertTrue(is_configured(), "Microsoft Agent 365 should be configured")

        # Get tracer to ensure it works
        tracer = get_tracer()
        self.assertIsNotNone(tracer, "Microsoft Agent 365 tracer should be available")

        # Create instrumentor
        self._test_instrumentor = CustomLangChainInstrumentor()

        # Verify the object was created
        self.assertIsNotNone(self._test_instrumentor)
        self.assertIsInstance(self._test_instrumentor, CustomLangChainInstrumentor)

        # Check if it has expected attributes/methods
        self.assertTrue(hasattr(self._test_instrumentor, "_instrument"))
        self.assertTrue(hasattr(self._test_instrumentor, "_uninstrument"))
        self.assertTrue(hasattr(self._test_instrumentor, "get_span"))
        self.assertTrue(hasattr(self._test_instrumentor, "get_ancestors"))

        # Check that tracer was created during initialization
        self.assertIsNotNone(
            self._test_instrumentor._tracer, "Tracer should be created after initialization"
        )

        print(
            "✅ Test 1: InstrumentorForLangChain initialization and Microsoft Agent 365 integration works"
        )

    def test_instrumentor_get_span_functionality(self):
        """Test 2: Verify get_span method works correctly with mock data."""
        self._test_instrumentor = CustomLangChainInstrumentor()

        # Test with non-existent run_id
        test_run_id = uuid4()
        span = self._test_instrumentor.get_span(test_run_id)
        self.assertIsNone(span, "get_span should return None for non-existent run_id")

        # Test with mock span data
        if self._test_instrumentor._tracer is not None:
            # Mock the internal _spans_by_run dict
            mock_span = MagicMock()
            self._test_instrumentor._tracer._spans_by_run[test_run_id] = mock_span

            result_span = self._test_instrumentor.get_span(test_run_id)
            self.assertEqual(result_span, mock_span, "get_span should return the correct span")

            # Clean up the mock data
            del self._test_instrumentor._tracer._spans_by_run[test_run_id]

        print("✅ Test 2: get_span functionality works correctly")

    def test_instrumentor_wrapping_mechanism(self):
        """Test 3: Verify instrumentor properly wraps LangChain BaseCallbackManager."""
        self._test_instrumentor = CustomLangChainInstrumentor()

        # Verify instrumentor has internal tracer
        self.assertIsNotNone(
            self._test_instrumentor._tracer, "Tracer should be created during instrumentation"
        )

        # Verify original callback init was saved
        self.assertIsNotNone(
            self._test_instrumentor._original_cb_init, "Original callback init should be saved"
        )

        # Verify get_span and get_ancestors methods work
        self.assertTrue(callable(self._test_instrumentor.get_span))
        self.assertTrue(callable(self._test_instrumentor.get_ancestors))

        # Test get_ancestors with empty result
        test_run_id = uuid4()
        ancestors = self._test_instrumentor.get_ancestors(test_run_id)
        self.assertEqual(
            ancestors, [], "get_ancestors should return empty list for non-existent run"
        )

        print("✅ Test 3: LangChain BaseCallbackManager wrapping works correctly")


def run_langchain_tests():
    """Run all LangChain wrapper tests with detailed output."""
    print("🧪 Running Microsoft Agent 365 LangChain Instrumentor tests...")
    print("=" * 80)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestInstrumentorLangChain))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 80)
    print("🏁 LangChain Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("🎉 All LangChain tests passed!")
        return True
    else:
        print("🔧 Some LangChain tests failed. Check output above.")
        return False


if __name__ == "__main__":
    success = run_langchain_tests()
    exit(0 if success else 1)

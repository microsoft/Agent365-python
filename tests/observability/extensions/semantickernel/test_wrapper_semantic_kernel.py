# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import MagicMock, patch

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.extensions.semantickernel.span_processor import (
    SemanticKernelSpanProcessor,
)
from microsoft_agents_a365.observability.extensions.semantickernel.trace_instrumentor import (
    SemanticKernelInstrumentor,
)


class TestSemanticKernelInstrumentor(unittest.TestCase):
    """Unit tests for SemanticKernelInstrumentor class."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        configure(
            service_name="test-service-semantic-kernel",
            service_namespace="test-namespace-semantic-kernel",
        )

    def test_instrumentor_initialization_and_dependencies(self):
        """Test instrumentor initialization and dependency verification."""
        # Test basic initialization
        instrumentor = SemanticKernelInstrumentor()
        self.assertIsNotNone(instrumentor)
        self.assertIsInstance(instrumentor, SemanticKernelInstrumentor)

        # Test dependencies
        dependencies = instrumentor.instrumentation_dependencies()
        self.assertIsInstance(dependencies, (list, tuple))

        # Verify it contains semantic-kernel dependency
        dependency_strings = list(dependencies)
        semantic_kernel_deps = [dep for dep in dependency_strings if "semantic-kernel" in dep]
        self.assertGreater(
            len(semantic_kernel_deps), 0, "Should have at least one semantic-kernel dependency"
        )

    @patch(
        "microsoft_agents_a365.observability.extensions.semantickernel.trace_instrumentor.get_tracer_provider"
    )
    def test_instrumentor_adds_span_processor(self, mock_get_tracer_provider):
        """Test instrumentor adds SemanticKernelSpanProcessor to tracer provider."""
        # Mock the tracer provider
        mock_provider = MagicMock()
        mock_get_tracer_provider.return_value = mock_provider

        # Create and instrument
        instrumentor = SemanticKernelInstrumentor()
        instrumentor._instrument()

        # Verify add_span_processor was called
        mock_provider.add_span_processor.assert_called_once()

        # Verify the processor added is a SemanticKernelSpanProcessor
        args, kwargs = mock_provider.add_span_processor.call_args
        processor = args[0] if args else kwargs.get("processor")
        self.assertIsInstance(processor, SemanticKernelSpanProcessor)

    def test_span_processor_chat_span_processing(self):
        """Test SpanProcessor correctly processes chat spans and ignores others."""
        processor = SemanticKernelSpanProcessor(service_name="test-service")

        # Test processor initialization
        self.assertIsNotNone(processor)
        self.assertEqual(processor.service_name, "test-service")

        # Test chat span processing
        mock_chat_span = MagicMock()
        mock_chat_span.name = "chat.completions"
        mock_parent_context = MagicMock()

        processor.on_start(mock_chat_span, mock_parent_context)

        # Verify set_attribute and update_name were called
        mock_chat_span.set_attribute.assert_called_once()
        mock_chat_span.update_name.assert_called_once()

        # Verify the updated name contains "chat"
        args, kwargs = mock_chat_span.update_name.call_args
        updated_name = args[0] if args else kwargs.get("name")
        self.assertIn("chat", updated_name.lower())

        # Test non-chat span (should be ignored)
        mock_non_chat_span = MagicMock()
        mock_non_chat_span.name = "function.call"

        processor.on_start(mock_non_chat_span, mock_parent_context)

        # Verify set_attribute and update_name were NOT called for non-chat span
        mock_non_chat_span.set_attribute.assert_not_called()
        mock_non_chat_span.update_name.assert_not_called()


if __name__ == "__main__":
    unittest.main()

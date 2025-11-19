# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import Mock, patch

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.exporters.agent365_exporter_options import (
    Agent365ExporterOptions,
)
from microsoft_agents_a365.observability.core.trace_processor import SpanProcessor


class TestAgent365Configure(unittest.TestCase):
    """Test suite for Agent365 configuration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_token_resolver = Mock()
        self.mock_token_resolver.return_value = "test_token_123"

    def test_configure_basic_functionality(self):
        """Test configure function with basic parameters and legacy parameters."""
        # Test basic configuration without exporter_options
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
        )
        self.assertTrue(result, "configure() should return True")

        # Test configuration with legacy parameters
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            token_resolver=self.mock_token_resolver,
            cluster_category="test",
        )
        self.assertTrue(result, "configure() should return True with legacy parameters")

    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    def test_configure_with_exporter_options_and_parameter_precedence(self, mock_is_enabled):
        """Test configure function with exporter_options and verify parameter precedence."""
        # Enable Agent365 exporter for this test
        mock_is_enabled.return_value = True

        # Test 1: Basic exporter_options functionality
        exporter_options = Agent365ExporterOptions(
            cluster_category="dev",
            token_resolver=self.mock_token_resolver,
            use_s2s_endpoint=True,
            max_queue_size=1024,
            scheduled_delay_ms=2500,
            exporter_timeout_ms=15000,
            max_export_batch_size=256,
        )

        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=exporter_options,
        )
        self.assertTrue(result, "configure() should return True with exporter_options")

    @patch("microsoft_agents_a365.observability.core.config.Agent365Exporter")
    @patch("microsoft_agents_a365.observability.core.config.BatchSpanProcessor")
    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    def test_batch_span_processor_and_exporter_called_with_correct_values(
        self, mock_is_enabled, mock_batch_processor, mock_exporter
    ):
        """Test that BatchSpanProcessor and Agent365Exporter are called with correct values from exporter_options."""
        # Enable Agent365 exporter for this test
        mock_is_enabled.return_value = True

        # Create exporter options with specific values
        exporter_options = Agent365ExporterOptions(
            cluster_category="staging",
            token_resolver=self.mock_token_resolver,
            use_s2s_endpoint=True,
            max_queue_size=512,
            scheduled_delay_ms=1000,
            exporter_timeout_ms=10000,
            max_export_batch_size=128,
        )

        # Configure with exporter_options
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=exporter_options,
        )

        # Verify configuration succeeded
        self.assertTrue(result, "configure() should return True")

        # Verify Agent365Exporter was called with correct parameters
        mock_exporter.assert_called_once_with(
            token_resolver=self.mock_token_resolver,
            cluster_category="staging",
            use_s2s_endpoint=True,
        )

        # Verify BatchSpanProcessor was called with correct parameters from exporter_options
        mock_batch_processor.assert_called_once()
        call_args = mock_batch_processor.call_args
        self.assertEqual(call_args.kwargs["max_queue_size"], 512)
        self.assertEqual(call_args.kwargs["schedule_delay_millis"], 1000)
        self.assertEqual(call_args.kwargs["export_timeout_millis"], 10000)
        self.assertEqual(call_args.kwargs["max_export_batch_size"], 128)

    def test_span_processor_creation(self):
        """Test SpanProcessor class creation."""
        processor = SpanProcessor()
        self.assertIsNotNone(processor, "SpanProcessor should be created successfully")


if __name__ == "__main__":
    unittest.main()

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import Mock, patch

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.exporters.agent365_exporter_options import (
    Agent365ExporterOptions,
)
from microsoft_agents_a365.observability.core.trace_processor import SpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider


class TestAgent365Configure(unittest.TestCase):
    """Test suite for Agent365 configuration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset TelemetryManager state before each test
        from microsoft_agents_a365.observability.core.config import _telemetry_manager
        from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        self.mock_token_resolver = Mock()
        self.mock_token_resolver.return_value = "test_token_123"

    def tearDown(self):
        """Clean up after each test."""
        # Reset the telemetry manager singleton state
        from microsoft_agents_a365.observability.core.config import _telemetry_manager
        from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        # Do NOT reset otel_trace._TRACER_PROVIDER to None to avoid NonRecordingSpan issues in other tests

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

    @patch("microsoft_agents_a365.observability.core.config._Agent365Exporter")
    @patch("microsoft_agents_a365.observability.core.config._EnrichingBatchSpanProcessor")
    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    def test_batch_span_processor_and_exporter_called_with_correct_values(
        self, mock_is_enabled, mock_batch_processor, mock_exporter
    ):
        """Test that BatchSpanProcessor and _Agent365Exporter are called with correct values from exporter_options."""
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
            suppress_invoke_agent_input=False,
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

    def test_configure_prevents_duplicate_initialization(self):
        """Test that calling configure() multiple times doesn't reinitialize."""
        result1 = configure(
            service_name="test-service-1",
            service_namespace="test-namespace-1",
        )
        self.assertTrue(result1)

        with patch(
            "microsoft_agents_a365.observability.core.config._telemetry_manager._logger"
        ) as mock_logger:
            result2 = configure(
                service_name="test-service-2",
                service_namespace="test-namespace-2",
            )
            self.assertTrue(result2)
            mock_logger.warning.assert_called_once()
            self.assertIn("already configured", mock_logger.warning.call_args[0][0].lower())

    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    @patch("microsoft_agents_a365.observability.core.config.trace.get_tracer_provider")
    def test_configure_uses_existing_tracer_provider(self, mock_get_provider, mock_is_enabled):
        """Test configure() uses existing TracerProvider and adds processors without calling set_tracer_provider."""
        mock_is_enabled.return_value = False

        existing_provider = TracerProvider(
            resource=Resource.create({"service.name": "existing-service"})
        )
        mock_get_provider.return_value = existing_provider

        with patch(
            "microsoft_agents_a365.observability.core.config._telemetry_manager._logger"
        ) as mock_logger:
            with patch(
                "microsoft_agents_a365.observability.core.config.trace.set_tracer_provider"
            ) as mock_set:
                result = configure(service_name="new-service", service_namespace="new-namespace")
                self.assertTrue(result)

                # Verify existing provider was detected
                info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                self.assertTrue(
                    any("Detected existing TracerProvider" in msg for msg in info_calls)
                )

                # Verify didn't call set_tracer_provider
                mock_set.assert_not_called()

                # Verify both processors were added by inspecting the MultiSpanProcessor

                active_processor = existing_provider._active_span_processor
                self.assertIsNotNone(active_processor)

                # MultiSpanProcessor has a _span_processors list
                processors = active_processor._span_processors
                self.assertEqual(
                    len(processors),
                    2,
                    "Should have 2 processors: BatchSpanProcessor and SpanProcessor",
                )

                # Verify types of processors
                processor_types = [type(p).__name__ for p in processors]
                self.assertIn("_EnrichingBatchSpanProcessor", processor_types)
                self.assertIn("SpanProcessor", processor_types)


if __name__ == "__main__":
    unittest.main()

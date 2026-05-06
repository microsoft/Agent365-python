# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import Mock, patch

from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.exporters.agent365_exporter_options import (
    Agent365ExporterOptions,
)
from microsoft_agents_a365.observability.core.exporters.enriched_span import (
    EnrichedReadableSpan,
)
from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
)
from microsoft_agents_a365.observability.core.exporters.spectra_exporter_options import (
    SpectraExporterOptions,
)
from opentelemetry.sdk.trace import ReadableSpan


class TestSpectraExporterOptions(unittest.TestCase):
    """Tests for SpectraExporterOptions class."""

    def test_spectra_exporter_options_defaults(self):
        """All default values are correct."""
        opts = SpectraExporterOptions()
        self.assertEqual(opts.endpoint, "http://localhost:4317")
        self.assertEqual(opts.protocol, "grpc")
        self.assertTrue(opts.insecure)
        self.assertEqual(opts.max_queue_size, 2048)
        self.assertEqual(opts.scheduled_delay_ms, 5000)
        self.assertEqual(opts.exporter_timeout_ms, 30000)
        self.assertEqual(opts.max_export_batch_size, 512)

    def test_spectra_exporter_options_http_default_endpoint(self):
        """HTTP protocol defaults to port 4318."""
        opts = SpectraExporterOptions(protocol="http")
        self.assertEqual(opts.endpoint, "http://localhost:4318")

    def test_spectra_exporter_options_explicit_endpoint_overrides_default(self):
        """Explicit endpoint overrides protocol-based default."""
        opts = SpectraExporterOptions(protocol="http", endpoint="http://custom:9999")
        self.assertEqual(opts.endpoint, "http://custom:9999")

    def test_spectra_options_invalid_protocol_raises(self):
        """ValueError for invalid protocol."""
        with self.assertRaises(ValueError) as ctx:
            SpectraExporterOptions(protocol="websocket")
        self.assertIn("websocket", str(ctx.exception))


class TestConfigureWithSpectraOptions(unittest.TestCase):
    """Tests for configure() with SpectraExporterOptions."""

    def setUp(self):
        from microsoft_agents_a365.observability.core.config import _telemetry_manager
        from microsoft_agents_a365.observability.core.opentelemetry_scope import (
            OpenTelemetryScope,
        )

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

    def tearDown(self):
        from microsoft_agents_a365.observability.core.config import _telemetry_manager
        from microsoft_agents_a365.observability.core.opentelemetry_scope import (
            OpenTelemetryScope,
        )

        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

    def test_configure_with_spectra_options_default(self):
        """configure() succeeds with SpectraExporterOptions() defaults."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(),
        )
        self.assertTrue(result)

    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    def test_configure_with_spectra_options_creates_grpc_exporter(self, mock_grpc):
        """gRPC OTLPSpanExporter created with correct endpoint and insecure args."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(),
        )
        self.assertTrue(result)
        mock_grpc.assert_called_once_with(
            endpoint="http://localhost:4317",
            insecure=True,
        )

    @patch("microsoft_agents_a365.observability.core.config.OTLPSpanExporter")
    def test_configure_with_spectra_options_creates_http_exporter(self, mock_http):
        """HTTP OTLPSpanExporter created when protocol='http'."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(protocol="http"),
        )
        self.assertTrue(result)
        mock_http.assert_called_once_with(
            endpoint="http://localhost:4318",
        )

    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    def test_configure_with_spectra_options_custom_endpoint(self, mock_grpc):
        """Custom endpoint passed through to exporter."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(endpoint="http://spectra-sidecar:4317"),
        )
        self.assertTrue(result)
        mock_grpc.assert_called_once_with(
            endpoint="http://spectra-sidecar:4317",
            insecure=True,
        )

    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    @patch.dict("os.environ", {"ENABLE_A365_OBSERVABILITY_EXPORTER": "true"})
    def test_configure_with_spectra_options_ignores_a365_env_var(self, mock_is_enabled, mock_grpc):
        """ENABLE_A365_OBSERVABILITY_EXPORTER=true doesn't create _Agent365Exporter."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(),
        )
        self.assertTrue(result)
        mock_grpc.assert_called_once()
        # is_agent365_exporter_enabled should not be called when Spectra path is taken
        mock_is_enabled.assert_not_called()

    @patch("microsoft_agents_a365.observability.core.config._EnrichingBatchSpanProcessor")
    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    def test_configure_with_spectra_options_batch_settings(self, mock_grpc, mock_batch):
        """Batch processor kwargs extracted from SpectraExporterOptions."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(
                max_queue_size=1024,
                scheduled_delay_ms=2000,
                exporter_timeout_ms=15000,
                max_export_batch_size=256,
            ),
        )
        self.assertTrue(result)
        mock_batch.assert_called_once()
        call_kwargs = mock_batch.call_args.kwargs
        self.assertEqual(call_kwargs["max_queue_size"], 1024)
        self.assertEqual(call_kwargs["schedule_delay_millis"], 2000)
        self.assertEqual(call_kwargs["export_timeout_millis"], 15000)
        self.assertEqual(call_kwargs["max_export_batch_size"], 256)

    @patch("microsoft_agents_a365.observability.core.config._Agent365Exporter")
    @patch("microsoft_agents_a365.observability.core.config.is_agent365_exporter_enabled")
    def test_configure_with_agent365_options_unchanged(self, mock_is_enabled, mock_exporter):
        """A365 regression test — existing path still works identically."""
        mock_is_enabled.return_value = True
        mock_token_resolver = Mock()
        mock_token_resolver.return_value = "token"

        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=Agent365ExporterOptions(
                cluster_category="staging",
                token_resolver=mock_token_resolver,
                use_s2s_endpoint=True,
            ),
        )
        self.assertTrue(result)
        mock_exporter.assert_called_once_with(
            token_resolver=mock_token_resolver,
            cluster_category="staging",
            use_s2s_endpoint=True,
            max_payload_bytes=900_000,
        )

    @patch("microsoft_agents_a365.observability.core.config.OTLPSpanExporter")
    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    @patch.dict("os.environ", {"ENABLE_OTLP_EXPORTER": "true"})
    def test_configure_spectra_with_otlp_bolt_on(self, mock_grpc, mock_http_otlp):
        """Spectra + ENABLE_OTLP_EXPORTER=true creates two exporters."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(),
        )
        self.assertTrue(result)
        # gRPC for Spectra
        mock_grpc.assert_called_once()
        # HTTP OTLP for bolt-on
        mock_http_otlp.assert_called_once()

    @patch("microsoft_agents_a365.observability.core.config._EnrichingBatchSpanProcessor")
    @patch("microsoft_agents_a365.observability.core.config.GrpcOTLPSpanExporter")
    def test_configure_spectra_with_suppress_invoke_agent_input(self, mock_grpc, mock_batch):
        """suppress_invoke_agent_input=True passed to batch processor."""
        result = configure(
            service_name="test-service",
            service_namespace="test-namespace",
            exporter_options=SpectraExporterOptions(),
            suppress_invoke_agent_input=True,
        )
        self.assertTrue(result)
        mock_batch.assert_called_once()
        call_kwargs = mock_batch.call_args.kwargs
        self.assertTrue(call_kwargs["suppress_invoke_agent_input"])


class TestEnrichedSpanExcludedAttributes(unittest.TestCase):
    """Tests for EnrichedReadableSpan excluded_attribute_keys."""

    def test_enriched_span_excluded_attribute_keys(self):
        """EnrichedReadableSpan with exclusions removes specified attributes."""
        mock_span = Mock(spec=ReadableSpan)
        mock_span.attributes = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        enriched = EnrichedReadableSpan(
            mock_span,
            extra_attributes={"key4": "value4"},
            excluded_attribute_keys={"key2"},
        )

        attrs = enriched.attributes
        self.assertEqual(attrs["key1"], "value1")
        self.assertNotIn("key2", attrs)
        self.assertEqual(attrs["key3"], "value3")
        self.assertEqual(attrs["key4"], "value4")


class TestSuppressInvokeAgentInputInProcessor(unittest.TestCase):
    """Tests for suppress_invoke_agent_input in _EnrichingBatchSpanProcessor."""

    def test_suppress_invoke_agent_input_strips_attribute_in_enriching_processor(self):
        """Processor strips gen_ai.input.messages from InvokeAgent spans."""
        mock_exporter = Mock()

        processor = _EnrichingBatchSpanProcessor(
            mock_exporter,
            suppress_invoke_agent_input=True,
        )

        mock_span = Mock(spec=ReadableSpan)
        mock_span.name = "invoke_agent test-agent"
        mock_span.attributes = {
            GEN_AI_OPERATION_NAME_KEY: INVOKE_AGENT_OPERATION_NAME,
            GEN_AI_INPUT_MESSAGES_KEY: '[{"role": "user", "content": "hello"}]',
            "other_key": "other_value",
        }

        with patch.object(_EnrichingBatchSpanProcessor, "on_end", wraps=processor.on_end):
            # Call on_end directly — the parent's on_end will queue the span
            # We patch super().on_end to capture what gets queued
            with patch(
                "microsoft_agents_a365.observability.core.exporters"
                ".enriching_span_processor.BatchSpanProcessor.on_end"
            ) as mock_super_on_end:
                processor.on_end(mock_span)

                # Verify super().on_end was called with an EnrichedReadableSpan
                mock_super_on_end.assert_called_once()
                enriched_span = mock_super_on_end.call_args[0][0]
                self.assertIsInstance(enriched_span, EnrichedReadableSpan)

                # Verify input messages were stripped
                attrs = enriched_span.attributes
                self.assertNotIn(GEN_AI_INPUT_MESSAGES_KEY, attrs)
                self.assertEqual(attrs["other_key"], "other_value")

        processor.shutdown()


if __name__ == "__main__":
    unittest.main()

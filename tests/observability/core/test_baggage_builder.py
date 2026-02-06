# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import unittest

from microsoft_agents_a365.observability.core.constants import (
    CORRELATION_ID_KEY,
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_BLUEPRINT_ID_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_UPN_KEY,
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    HIRING_MANAGER_ID_KEY,
    OPERATION_SOURCE_KEY,
    SESSION_DESCRIPTION_KEY,
    SESSION_ID_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
from microsoft_agents_a365.observability.core.models.operation_source import OperationSource
from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestBaggageBuilder(unittest.TestCase):
    """Test the BaggageBuilder class."""

    @classmethod
    def setUpClass(cls):
        """Save the original tracer provider."""
        cls._original_provider = trace.get_tracer_provider()

    @classmethod
    def tearDownClass(cls):
        """Restore the original tracer provider."""
        if hasattr(cls, "_original_provider"):
            trace.set_tracer_provider(cls._original_provider)
        # Force OpenTelemetryScope to refresh its tracer
        from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope

        OpenTelemetryScope._tracer = None

    def setUp(self):
        """Set up test fixtures."""
        # Enable telemetry for tests
        os.environ["ENABLE_OBSERVABILITY"] = "true"

        # Clear any existing context/baggage before each test
        context.detach(context.attach({}))

        # Create a fresh BaggageBuilder for each test
        self.builder = BaggageBuilder()

    def tearDown(self):
        """Clean up after each test."""
        # Clear context
        context.detach(context.attach({}))

    def test_baggage_builder_sets_values(self):
        """Test that BaggageBuilder sets baggage values correctly."""
        tenant = "tenant-1"
        agent = "agent-1"
        corr = "corr-1"

        # Use the baggage builder within a context
        with BaggageBuilder().tenant_id(tenant).agent_id(agent).correlation_id(corr).build():
            # Assert inside scope - baggage should be set
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(TENANT_ID_KEY), tenant)
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_ID_KEY), agent)
            self.assertEqual(current_baggage.get(CORRELATION_ID_KEY), corr)

        # Assert after exiting scope - baggage should be restored/cleared
        current_baggage = baggage.get_all()
        self.assertIsNone(current_baggage.get(TENANT_ID_KEY))
        self.assertIsNone(current_baggage.get(GEN_AI_AGENT_ID_KEY))
        self.assertIsNone(current_baggage.get(CORRELATION_ID_KEY))
        print("✅ BaggageBuilder sets and restores values correctly!")

    def test_all_baggage_keys(self):
        """Test all baggage key setter methods."""
        with (
            BaggageBuilder()
            .operation_source(OperationSource.SDK)
            .tenant_id("tenant-1")
            .agent_id("agent-1")
            .agent_auid("auid-1")
            .agent_upn("upn-1")
            .agent_blueprint_id("blueprint-1")
            .correlation_id("corr-1")
            .caller_id("caller-1")
            .caller_client_ip("192.168.1.100")
            .hiring_manager_id("manager-1")
            .build()
        ):
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(OPERATION_SOURCE_KEY), OperationSource.SDK.value)
            self.assertEqual(current_baggage.get(TENANT_ID_KEY), "tenant-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_ID_KEY), "agent-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_AUID_KEY), "auid-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_UPN_KEY), "upn-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY), "blueprint-1")
            self.assertEqual(current_baggage.get(CORRELATION_ID_KEY), "corr-1")
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_ID_KEY), "caller-1")
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "192.168.1.100")
            self.assertEqual(current_baggage.get(HIRING_MANAGER_ID_KEY), "manager-1")
        print("✅ All baggage keys work correctly!")

    def test_baggage_propagates_to_child_spans(self):
        """Test that baggage values are copied as attributes onto parent and child spans via SpanProcessor."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Also add the Microsoft Agent 365 span processor directly
        from microsoft_agents_a365.observability.core.trace_processor.span_processor import (
            SpanProcessor as Agent365SpanProcessor,
        )

        agent365_processor = Agent365SpanProcessor()
        provider.add_span_processor(agent365_processor)

        tracer = provider.get_tracer(__name__)

        tenant = "tenant-propagation-test"
        agent = "agent-propagation-test"

        # Create baggage before starting spans so processor can copy it
        with BaggageBuilder().tenant_id(tenant).agent_id(agent).build():
            with tracer.start_as_current_span("parent_span"):
                # Nested child span should also receive baggage-derived attributes at start
                with tracer.start_as_current_span("child_span"):
                    pass  # Just create the spans, attributes are set by the processor

        # Ensure spans exported contain these attributes (export happens on end)
        finished_spans = exporter.get_finished_spans()
        # Find parent and child by name
        names = {s.name: s for s in finished_spans}
        self.assertIn("parent_span", names, "parent_span not exported")
        self.assertIn("child_span", names, "child_span not exported")
        self.assertEqual(names["parent_span"].attributes.get(TENANT_ID_KEY), tenant)
        self.assertEqual(names["parent_span"].attributes.get(GEN_AI_AGENT_ID_KEY), agent)
        self.assertEqual(names["child_span"].attributes.get(TENANT_ID_KEY), tenant)
        self.assertEqual(names["child_span"].attributes.get(GEN_AI_AGENT_ID_KEY), agent)

    def test_baggage_reset_after_scope_exit(self):
        """Test that all baggage values are completely reset/cleared after exiting scope."""
        # First, set some initial baggage values outside the builder scope
        initial_ctx = baggage.set_baggage("existing_key", "existing_value")
        context.attach(initial_ctx)

        # Verify initial baggage exists
        initial_baggage = baggage.get_all()
        self.assertEqual(initial_baggage.get("existing_key"), "existing_value")

        # Use BaggageBuilder to set all possible values
        with (
            BaggageBuilder()
            .operation_source(OperationSource.SDK)
            .tenant_id("test-tenant")
            .agent_id("test-agent")
            .agent_auid("test-auid")
            .agent_upn("test-upn")
            .agent_blueprint_id("test-blueprint")
            .correlation_id("test-correlation")
            .caller_id("test-caller")
            .hiring_manager_id("test-manager")
            .build()
        ):
            # Inside scope - verify all baggage values are set
            scoped_baggage = baggage.get_all()
            self.assertEqual(scoped_baggage.get(OPERATION_SOURCE_KEY), OperationSource.SDK.value)
            self.assertEqual(scoped_baggage.get(TENANT_ID_KEY), "test-tenant")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_ID_KEY), "test-agent")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_AUID_KEY), "test-auid")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_UPN_KEY), "test-upn")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY), "test-blueprint")
            self.assertEqual(scoped_baggage.get(CORRELATION_ID_KEY), "test-correlation")
            self.assertEqual(scoped_baggage.get(GEN_AI_CALLER_ID_KEY), "test-caller")
            self.assertEqual(scoped_baggage.get(HIRING_MANAGER_ID_KEY), "test-manager")
            # Original baggage should still exist
            self.assertEqual(scoped_baggage.get("existing_key"), "existing_value")

        # After exiting scope - verify ALL BaggageBuilder values are cleared
        final_baggage = baggage.get_all()

        # All BaggageBuilder keys should be None/cleared
        self.assertIsNone(final_baggage.get(OPERATION_SOURCE_KEY))
        self.assertIsNone(final_baggage.get(TENANT_ID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_ID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_AUID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_UPN_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY))
        self.assertIsNone(final_baggage.get(CORRELATION_ID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_CALLER_ID_KEY))
        self.assertIsNone(final_baggage.get(HIRING_MANAGER_ID_KEY))

        # Original baggage should be restored
        self.assertEqual(final_baggage.get("existing_key"), "existing_value")

        print("✅ All baggage values are properly reset after scope exit!")

    def test_set_pairs_accepts_dict_and_iterable(self):
        """set_pairs should accept both dict and iterable[(k,v)] and apply them to baggage."""
        dict_pairs = {
            TENANT_ID_KEY: "tenant-x",
            GEN_AI_AGENT_ID_KEY: "agent-x",
            CORRELATION_ID_KEY: "corr-x",
        }
        iter_pairs = [
            (GEN_AI_AGENT_AUID_KEY, "auid-x"),
            (GEN_AI_AGENT_UPN_KEY, "upn-x"),
        ]

        # Also verify that None / whitespace values are ignored
        dict_pairs_with_ignored = {
            OPERATION_SOURCE_KEY: OperationSource.SDK.value,
            GEN_AI_CALLER_ID_KEY: None,  # ignored
        }
        iter_pairs_with_ignored = [
            (HIRING_MANAGER_ID_KEY, "  "),  # ignored (whitespace)
        ]

        with (
            BaggageBuilder()
            .set_pairs(dict_pairs)
            .set_pairs(iter_pairs)
            .set_pairs(dict_pairs_with_ignored)
            .set_pairs(iter_pairs_with_ignored)
            .build()
        ):
            baggage_contents = baggage.get_all()
            self.assertEqual(baggage_contents.get(TENANT_ID_KEY), "tenant-x")
            self.assertEqual(baggage_contents.get(GEN_AI_AGENT_ID_KEY), "agent-x")
            self.assertEqual(baggage_contents.get(CORRELATION_ID_KEY), "corr-x")
            self.assertEqual(baggage_contents.get(GEN_AI_AGENT_AUID_KEY), "auid-x")
            self.assertEqual(baggage_contents.get(GEN_AI_AGENT_UPN_KEY), "upn-x")
            self.assertEqual(baggage_contents.get(OPERATION_SOURCE_KEY), OperationSource.SDK.value)
            # Ignored values should not be present
            self.assertIsNone(baggage_contents.get(GEN_AI_CALLER_ID_KEY))
            self.assertIsNone(baggage_contents.get(HIRING_MANAGER_ID_KEY))

    def test_source_metadata_name_method(self):
        """Test deprecated source_metadata_name method - should delegate to channel_name."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "source_metadata_name"))
        self.assertTrue(callable(self.builder.source_metadata_name))

        # Should set channel name baggage through delegation
        with self.builder.source_metadata_name("test-channel").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_EXECUTION_SOURCE_NAME_KEY), "test-channel")

    def test_source_metadata_description_method(self):
        """Test deprecated source_metadata_description method - should delegate to channel_links."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "source_metadata_description"))
        self.assertTrue(callable(self.builder.source_metadata_description))

        # Should set channel description baggage through delegation
        with self.builder.source_metadata_description("test-description").build():
            current_baggage = baggage.get_all()
            self.assertEqual(
                current_baggage.get(GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY), "test-description"
            )

    def test_session_id_method(self):
        """Test session_id method sets session ID baggage."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "session_id"))
        self.assertTrue(callable(self.builder.session_id))

        # Should set session ID baggage
        with self.builder.session_id("test-session-123").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SESSION_ID_KEY), "test-session-123")

    def test_session_description_method(self):
        """Test session_description method sets session description baggage."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "session_description"))
        self.assertTrue(callable(self.builder.session_description))

        # Should set session description baggage
        with self.builder.session_description("test session description").build():
            current_baggage = baggage.get_all()
            self.assertEqual(
                current_baggage.get(SESSION_DESCRIPTION_KEY), "test session description"
            )

    def test_channel_name_method(self):
        """Test channel_name method sets channel name baggage."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "channel_name"))
        self.assertTrue(callable(self.builder.channel_name))

        # Should set channel name baggage
        with self.builder.channel_name("Teams Channel").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_EXECUTION_SOURCE_NAME_KEY), "Teams Channel")

    def test_channel_links_method(self):
        """Test channel_links method sets channel description baggage."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "channel_links"))
        self.assertTrue(callable(self.builder.channel_links))

        # Should set channel description baggage
        with self.builder.channel_links("https://teams.microsoft.com/channel/123").build():
            current_baggage = baggage.get_all()
            self.assertEqual(
                current_baggage.get(GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY),
                "https://teams.microsoft.com/channel/123",
            )

    def test_caller_client_ip_method(self):
        """Test caller_client_ip method sets client IP baggage with validation."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "caller_client_ip"))
        self.assertTrue(callable(self.builder.caller_client_ip))

        # Test valid IPv4 address
        with BaggageBuilder().caller_client_ip("192.168.1.100").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "192.168.1.100")

        # Test valid IPv6 address
        with BaggageBuilder().caller_client_ip("2001:db8::1").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "2001:db8::1")

        # Test None value (should not set baggage)
        with BaggageBuilder().caller_client_ip(None).build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY))

        # Test invalid IP address (should be handled gracefully now)
        with BaggageBuilder().caller_client_ip("not.an.ip.address").build():
            current_baggage = baggage.get_all()
            # Should be None due to proper exception handling
            self.assertIsNone(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY))


if __name__ == "__main__":
    unittest.main()

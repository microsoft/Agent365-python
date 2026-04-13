# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import unittest

from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_BLUEPRINT_ID_KEY,
    GEN_AI_AGENT_EMAIL_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_VERSION_KEY,
    GEN_AI_CALLER_CLIENT_IP_KEY,
    SERVER_ADDRESS_KEY,
    SERVER_PORT_KEY,
    SERVICE_NAME_KEY,
    SESSION_DESCRIPTION_KEY,
    SESSION_ID_KEY,
    TENANT_ID_KEY,
    USER_ID_KEY,
)
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
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

        # Use the baggage builder within a context
        with BaggageBuilder().tenant_id(tenant).agent_id(agent).build():
            # Assert inside scope - baggage should be set
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(TENANT_ID_KEY), tenant)
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_ID_KEY), agent)

        # Assert after exiting scope - baggage should be restored/cleared
        current_baggage = baggage.get_all()
        self.assertIsNone(current_baggage.get(TENANT_ID_KEY))
        self.assertIsNone(current_baggage.get(GEN_AI_AGENT_ID_KEY))
        print("✅ BaggageBuilder sets and restores values correctly!")

    def test_all_baggage_keys(self):
        """Test all baggage key setter methods."""
        with (
            BaggageBuilder()
            .tenant_id("tenant-1")
            .agent_id("agent-1")
            .agentic_user_id("auid-1")
            .agentic_user_email("upn-1")
            .agent_blueprint_id("blueprint-1")
            .user_id("caller-1")
            .user_client_ip("192.168.1.100")
            .build()
        ):
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(TENANT_ID_KEY), "tenant-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_ID_KEY), "agent-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_AUID_KEY), "auid-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_EMAIL_KEY), "upn-1")
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY), "blueprint-1")
            self.assertEqual(current_baggage.get(USER_ID_KEY), "caller-1")
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "192.168.1.100")
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
            .tenant_id("test-tenant")
            .agent_id("test-agent")
            .agentic_user_id("test-auid")
            .agentic_user_email("test-upn")
            .agent_blueprint_id("test-blueprint")
            .user_id("test-caller")
            .build()
        ):
            # Inside scope - verify all baggage values are set
            scoped_baggage = baggage.get_all()
            self.assertEqual(scoped_baggage.get(TENANT_ID_KEY), "test-tenant")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_ID_KEY), "test-agent")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_AUID_KEY), "test-auid")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_EMAIL_KEY), "test-upn")
            self.assertEqual(scoped_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY), "test-blueprint")
            self.assertEqual(scoped_baggage.get(USER_ID_KEY), "test-caller")
            # Original baggage should still exist
            self.assertEqual(scoped_baggage.get("existing_key"), "existing_value")

        # After exiting scope - verify ALL BaggageBuilder values are cleared
        final_baggage = baggage.get_all()

        # All BaggageBuilder keys should be None/cleared
        self.assertIsNone(final_baggage.get(TENANT_ID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_ID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_AUID_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_EMAIL_KEY))
        self.assertIsNone(final_baggage.get(GEN_AI_AGENT_BLUEPRINT_ID_KEY))
        self.assertIsNone(final_baggage.get(USER_ID_KEY))

        # Original baggage should be restored
        self.assertEqual(final_baggage.get("existing_key"), "existing_value")

        print("✅ All baggage values are properly reset after scope exit!")

    def test_set_pairs_accepts_dict_and_iterable(self):
        """set_pairs should accept both dict and iterable[(k,v)] and apply them to baggage."""
        dict_pairs = {
            TENANT_ID_KEY: "tenant-x",
            GEN_AI_AGENT_ID_KEY: "agent-x",
        }
        iter_pairs = [
            (GEN_AI_AGENT_AUID_KEY, "auid-x"),
            (GEN_AI_AGENT_EMAIL_KEY, "upn-x"),
        ]

        # Also verify that None / whitespace values are ignored
        dict_pairs_with_ignored = {
            USER_ID_KEY: None,  # ignored
        }
        iter_pairs_with_ignored = [
            (SESSION_ID_KEY, "  "),  # ignored (whitespace)
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
            self.assertEqual(baggage_contents.get(GEN_AI_AGENT_AUID_KEY), "auid-x")
            self.assertEqual(baggage_contents.get(GEN_AI_AGENT_EMAIL_KEY), "upn-x")
            # Ignored values should not be present
            self.assertIsNone(baggage_contents.get(USER_ID_KEY))
            self.assertIsNone(baggage_contents.get(SESSION_ID_KEY))

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
            self.assertEqual(current_baggage.get(CHANNEL_NAME_KEY), "Teams Channel")

    def test_channel_links_method(self):
        """Test channel_links method sets channel description baggage."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "channel_links"))
        self.assertTrue(callable(self.builder.channel_links))

        # Should set channel description baggage
        with self.builder.channel_links("https://teams.microsoft.com/channel/123").build():
            current_baggage = baggage.get_all()
            self.assertEqual(
                current_baggage.get(CHANNEL_LINK_KEY),
                "https://teams.microsoft.com/channel/123",
            )

    def test_user_client_ip_method(self):
        """Test user_client_ip method sets client IP baggage with validation."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "user_client_ip"))
        self.assertTrue(callable(self.builder.user_client_ip))

        # Test valid IPv4 address
        with BaggageBuilder().user_client_ip("192.168.1.100").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "192.168.1.100")

        # Test valid IPv6 address
        with BaggageBuilder().user_client_ip("2001:db8::1").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY), "2001:db8::1")

        # Test None value (should not set baggage)
        with BaggageBuilder().user_client_ip(None).build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY))

        # Test invalid IP address (should be handled gracefully now)
        with BaggageBuilder().user_client_ip("not.an.ip.address").build():
            current_baggage = baggage.get_all()
            # Should be None due to proper exception handling
            self.assertIsNone(current_baggage.get(GEN_AI_CALLER_CLIENT_IP_KEY))

    def test_operation_source_method(self):
        """Test operation_source method sets service name baggage using string values."""
        # Should exist and be callable
        self.assertTrue(hasattr(self.builder, "operation_source"))
        self.assertTrue(callable(self.builder.operation_source))

        # Test with custom service name
        with BaggageBuilder().operation_source("my-agent-service").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVICE_NAME_KEY), "my-agent-service")

        # Test with another service name
        with BaggageBuilder().operation_source("weather-bot").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVICE_NAME_KEY), "weather-bot")

        # Test with SDK as string
        with BaggageBuilder().operation_source("SDK").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVICE_NAME_KEY), "SDK")

        # Test with None value (should not set baggage)
        with BaggageBuilder().operation_source(None).build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(SERVICE_NAME_KEY))

        # Test with whitespace-only value (should not set baggage)
        with BaggageBuilder().operation_source("   ").build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(SERVICE_NAME_KEY))

    def test_invoke_agent_server_sets_address_and_port(self):
        """Test that invoke_agent_server sets both address and non-443 port."""
        address = "app.azurewebsites.net"
        port = 8080

        with BaggageBuilder().invoke_agent_server(address, port).build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVER_ADDRESS_KEY), address)
            self.assertEqual(current_baggage.get(SERVER_PORT_KEY), str(port))

        # After scope exit, baggage should be cleared
        current_baggage = baggage.get_all()
        self.assertIsNone(current_baggage.get(SERVER_ADDRESS_KEY))
        self.assertIsNone(current_baggage.get(SERVER_PORT_KEY))

    def test_invoke_agent_server_omits_port_when_443(self):
        """Test that invoke_agent_server omits port when it is the default 443."""
        address = "app.azurewebsites.net"

        with BaggageBuilder().invoke_agent_server(address, 443).build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVER_ADDRESS_KEY), address)
            self.assertIsNone(current_baggage.get(SERVER_PORT_KEY))

    def test_invoke_agent_server_sets_address_only_when_port_none(self):
        """Test that invoke_agent_server sets only address when port is None."""
        address = "app.azurewebsites.net"

        with BaggageBuilder().invoke_agent_server(address).build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(SERVER_ADDRESS_KEY), address)
            self.assertIsNone(current_baggage.get(SERVER_PORT_KEY))

    def test_agent_version_method(self):
        """Test agent_version method sets agent version baggage."""
        self.assertTrue(hasattr(self.builder, "agent_version"))
        self.assertTrue(callable(self.builder.agent_version))

        with self.builder.agent_version("1.0.0").build():
            current_baggage = baggage.get_all()
            self.assertEqual(current_baggage.get(GEN_AI_AGENT_VERSION_KEY), "1.0.0")

    def test_agent_version_none_not_set(self):
        """Test agent_version with None does not set baggage."""
        with BaggageBuilder().agent_version(None).build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(GEN_AI_AGENT_VERSION_KEY))

    def test_agent_version_whitespace_not_set(self):
        """Test agent_version with whitespace-only value does not set baggage."""
        with BaggageBuilder().agent_version("   ").build():
            current_baggage = baggage.get_all()
            self.assertIsNone(current_baggage.get(GEN_AI_AGENT_VERSION_KEY))


if __name__ == "__main__":
    unittest.main()

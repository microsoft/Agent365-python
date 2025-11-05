# Copyright (c) Microsoft. All rights reserved.


import os
import unittest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from microsoft_agents_a365.observability.core import AgentDetails, TenantDetails
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope


class TestRecordAttributes(unittest.TestCase):
    """Test the record_attributes method on OpenTelemetryScope."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        # Enable telemetry for tests
        os.environ["ENABLE_OBSERVABILITY"] = "true"

        # Set up a tracer with in-memory exporter for testing
        cls.exporter = InMemorySpanExporter()

        # Try to get existing provider, or create a new one
        try:
            provider = trace.get_tracer_provider()
            # Check if it's the default NoOp provider
            if isinstance(provider, trace.ProxyTracerProvider) or not hasattr(
                provider, "add_span_processor"
            ):
                # Create a new provider if it's NoOp
                provider = TracerProvider()
                trace.set_tracer_provider(provider)
        except Exception:
            # Create a new provider
            provider = TracerProvider()
            try:
                trace.set_tracer_provider(provider)
            except Exception:
                pass  # Provider already set

        # Add our span processor to whatever provider we have
        if hasattr(provider, "add_span_processor"):
            provider.add_span_processor(SimpleSpanProcessor(cls.exporter))

        # Force OpenTelemetryScope to use the new tracer
        OpenTelemetryScope._tracer = None

    def setUp(self):
        """Clear spans before each test."""
        # Force OpenTelemetryScope to refresh its tracer reference
        OpenTelemetryScope._tracer = None
        self.exporter.clear()

    def tearDown(self):
        """Clean up after each test."""
        # Clear exported spans
        self.exporter.clear()

    def test_record_attributes_with_dict(self):
        """Test recording attributes using a dictionary."""
        agent_details = AgentDetails(
            agent_id="test-agent", agent_name="Test Agent", agent_description="A test agent"
        )
        tenant_details = TenantDetails(tenant_id="test-tenant")

        with OpenTelemetryScope(
            kind="Internal",
            operation_name="test_operation",
            activity_name="test_activity",
            agent_details=agent_details,
            tenant_details=tenant_details,
        ) as scope:
            # Record custom attributes using a dictionary
            attributes = {
                "custom.attribute.1": "value1",
                "custom.attribute.2": 42,
                "custom.attribute.3": True,
            }
            scope.record_attributes(attributes)

        # Verify the attributes were set
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)

        span_attributes = spans[0].attributes
        self.assertEqual(span_attributes.get("custom.attribute.1"), "value1")
        self.assertEqual(span_attributes.get("custom.attribute.2"), 42)
        self.assertEqual(span_attributes.get("custom.attribute.3"), True)
        print("✅ record_attributes with dict works correctly!")

    def test_record_attributes_multiple_calls(self):
        """Test that multiple calls to record_attributes accumulate attributes."""
        agent_details = AgentDetails(agent_id="test-agent")

        with OpenTelemetryScope(
            kind="Internal",
            operation_name="test_operation",
            activity_name="test_activity",
            agent_details=agent_details,
        ) as scope:
            # First batch of attributes
            scope.record_attributes({"batch1.key1": "value1", "batch1.key2": "value2"})

            # Second batch of attributes
            scope.record_attributes({"batch2.key1": "value3", "batch2.key2": "value4"})

        # Verify all attributes were set
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)

        span_attributes = spans[0].attributes
        self.assertEqual(span_attributes.get("batch1.key1"), "value1")
        self.assertEqual(span_attributes.get("batch1.key2"), "value2")
        self.assertEqual(span_attributes.get("batch2.key1"), "value3")
        self.assertEqual(span_attributes.get("batch2.key2"), "value4")
        print("✅ Multiple calls to record_attributes accumulate correctly!")

    def test_record_attributes_with_telemetry_disabled(self):
        """Test that record_attributes is a no-op when telemetry is disabled."""
        # Save current state
        old_value = os.environ.get("ENABLE_OBSERVABILITY")

        try:
            # Disable telemetry
            os.environ["ENABLE_OBSERVABILITY"] = "false"

            agent_details = AgentDetails(agent_id="test-agent")

            with OpenTelemetryScope(
                kind="Internal",
                operation_name="test_operation",
                activity_name="test_activity",
                agent_details=agent_details,
            ) as scope:
                # This should be a no-op
                scope.record_attributes({"custom.key": "value"})

            # Verify no spans were created (the earlier ones might still be there)
            # We just verify that no new span with our custom key was added
            spans = self.exporter.get_finished_spans()
            # Check if any span has our custom attribute (none should)
            has_custom_key = any("custom.key" in (s.attributes or {}) for s in spans)
            self.assertFalse(has_custom_key)

            print("✅ record_attributes is no-op when telemetry disabled!")
        finally:
            # Restore telemetry state
            if old_value is not None:
                os.environ["ENABLE_OBSERVABILITY"] = old_value
            else:
                os.environ.pop("ENABLE_OBSERVABILITY", None)
            # Re-enable for safety
            os.environ["ENABLE_OBSERVABILITY"] = "true"


if __name__ == "__main__":
    unittest.main()

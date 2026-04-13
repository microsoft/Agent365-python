# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import unittest
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    Channel,
    InferenceCallDetails,
    InferenceOperationType,
    InferenceScope,
    Request,
    SpanDetails,
    configure,
    extract_context_from_headers,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
)
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestInferenceScope(unittest.TestCase):
    """Unit tests for InferenceScope and related classes."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Microsoft Agent 365 for testing
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"

        configure(
            service_name="test-inference-service",
            service_namespace="test-namespace",
        )
        # Create test agent details
        cls.agent_details = AgentDetails(agent_id="test-inference-agent")

    def setUp(self):
        super().setUp()

        # Reset TelemetryManager state to ensure fresh configuration
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        # Reconfigure to get a fresh TracerProvider
        configure(
            service_name="test-inference-service",
            service_namespace="test-namespace",
        )

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()

        self.span_exporter.clear()

    def test_inference_operation_type_enum(self):
        """Test InferenceOperationType enum values."""
        # Test enum values exist
        self.assertIsNotNone(InferenceOperationType.CHAT)
        self.assertIsNotNone(InferenceOperationType.TEXT_COMPLETION)
        self.assertIsNotNone(InferenceOperationType.GENERATE_CONTENT)

    def test_inference_call_details_creation(self):
        """Test InferenceCallDetails creation with required fields."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        self.assertEqual(details.operationName, InferenceOperationType.CHAT)
        self.assertEqual(details.model, "gpt-4")
        self.assertEqual(details.providerName, "openai")
        self.assertIsNone(details.inputTokens)
        self.assertIsNone(details.outputTokens)
        self.assertIsNone(details.finishReasons)

    def test_inference_call_details_with_all_fields(self):
        """Test InferenceCallDetails creation with all fields."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.TEXT_COMPLETION,
            model="gpt-3.5-turbo",
            providerName="azure-openai",
            inputTokens=150,
            outputTokens=75,
            finishReasons=["stop"],
        )

        self.assertEqual(details.operationName, InferenceOperationType.TEXT_COMPLETION)
        self.assertEqual(details.model, "gpt-3.5-turbo")
        self.assertEqual(details.providerName, "azure-openai")
        self.assertEqual(details.inputTokens, 150)
        self.assertEqual(details.outputTokens, 75)
        self.assertEqual(details.finishReasons, ["stop"])

    def test_inference_scope_start_method(self):
        """Test InferenceScope.start() static method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        # Scope might be None if telemetry is disabled
        if scope is not None:
            self.assertIsInstance(scope, InferenceScope)
            # Test that it has context manager methods
            self.assertTrue(hasattr(scope, "__enter__"))
            self.assertTrue(hasattr(scope, "__exit__"))
            self.assertTrue(hasattr(scope, "dispose"))

    def test_inference_scope_with_request(self):
        """Test InferenceScope with request parameter."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        request = Request(
            content="What is the weather like?",
            session_id="test-session-123",
        )

        scope = InferenceScope.start(request, details, self.agent_details)

        # Test that scope can be created with request
        if scope is not None:
            self.assertIsInstance(scope, InferenceScope)

    def test_request_metadata_set_on_span(self):
        """Test that request source metadata is set on span attributes."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        request = Request(
            content="Inference request with source metadata",
            session_id="session-meta",
            channel=Channel(name="Channel 1", link="Link to channel"),
        )

        scope = InferenceScope.start(request, details, self.agent_details)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            CHANNEL_NAME_KEY,
            span_attributes,
            "Expected source name to be set on span",
        )
        self.assertEqual(
            span_attributes[CHANNEL_NAME_KEY],
            request.channel.name,
        )

        self.assertIn(
            CHANNEL_LINK_KEY,
            span_attributes,
            "Expected source description to be set on span",
        )
        self.assertEqual(
            span_attributes[CHANNEL_LINK_KEY],
            request.channel.link,
        )

    def test_inference_scope_context_manager(self):
        """Test InferenceScope as context manager."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
            inputTokens=100,
            outputTokens=50,
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test context manager usage
            with scope as ctx_scope:
                self.assertIs(ctx_scope, scope)

                # Test optional recording methods if they exist
                if hasattr(scope, "record_input_tokens"):
                    scope.record_input_tokens(120)

                if hasattr(scope, "record_output_tokens"):
                    scope.record_output_tokens(60)

                if hasattr(scope, "record_finish_reasons"):
                    scope.record_finish_reasons(["stop", "length"])

    def test_inference_scope_dispose(self):
        """Test InferenceScope dispose method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test manual dispose
            scope.dispose()
            # Should not raise an exception
            self.assertIsInstance(scope, InferenceScope)

    def test_record_input_messages(self):
        """Test record_input_messages method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording input messages
            messages = ["Hello", "How are you?"]
            scope.record_input_messages(messages)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_input_messages"))

    def test_record_output_messages(self):
        """Test record_output_messages method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording output messages
            messages = ["I'm doing well", "Thanks for asking!"]
            scope.record_output_messages(messages)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_output_messages"))

    def test_record_input_tokens(self):
        """Test record_input_tokens method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording input tokens
            scope.record_input_tokens(150)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_input_tokens"))

    def test_record_output_tokens(self):
        """Test record_output_tokens method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording output tokens
            scope.record_output_tokens(75)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_output_tokens"))

    def test_record_finish_reasons(self):
        """Test record_finish_reasons method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording finish reasons
            finish_reasons = ["stop", "length"]
            scope.record_finish_reasons(finish_reasons)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_finish_reasons"))

    def test_record_thought_process(self):
        """Test record_thought_process method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(Request(), details, self.agent_details)

        if scope is not None:
            # Test recording thought process
            thought_process = "Analyzing user input and generating appropriate response"
            scope.record_thought_process(thought_process)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_thought_process"))

    def test_inference_scope_with_parent_context(self):
        """Test InferenceScope uses parent_context to link span to parent context."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        parent_trace_id = "1234567890abcdef1234567890abcdef"
        parent_span_id = "abcdefabcdef1234"
        traceparent = f"00-{parent_trace_id}-{parent_span_id}-01"

        # Extract context from traceparent header
        parent_context = extract_context_from_headers({"traceparent": traceparent})

        with InferenceScope.start(
            Request(),
            details,
            self.agent_details,
            span_details=SpanDetails(parent_context=parent_context),
        ):
            pass

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]

        # Verify span inherits parent's trace_id
        span_trace_id = f"{span.context.trace_id:032x}"
        self.assertEqual(span_trace_id, parent_trace_id)

        # Verify span's parent_span_id matches
        self.assertIsNotNone(span.parent, "Expected span to have a parent")
        self.assertTrue(hasattr(span.parent, "span_id"), "Expected parent to have span_id")
        span_parent_id = f"{span.parent.span_id:016x}"
        self.assertEqual(span_parent_id, parent_span_id)


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

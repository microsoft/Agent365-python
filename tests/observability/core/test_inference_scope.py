# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
import sys
import unittest
import pytest

from microsoft_agents_a365.observability.core import (
    ExecutionType,
    InferenceCallDetails,
    InferenceOperationType,
    InferenceScope,
    Request,
    SourceMetadata,
    TenantDetails,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
)
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
        # Create test agent and tenant details
        cls.agent_details = AgentDetails(agent_id="test-inference-agent")
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")

    def setUp(self):
        super().setUp()

        # Set up tracer to capture spans
        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))
        # trace.set_tracer_provider(tracer_provider)

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
        self.assertIsNone(details.responseId)

    def test_inference_call_details_with_all_fields(self):
        """Test InferenceCallDetails creation with all fields."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.TEXT_COMPLETION,
            model="gpt-3.5-turbo",
            providerName="azure-openai",
            inputTokens=150,
            outputTokens=75,
            finishReasons=["stop"],
            responseId="resp-123",
        )

        self.assertEqual(details.operationName, InferenceOperationType.TEXT_COMPLETION)
        self.assertEqual(details.model, "gpt-3.5-turbo")
        self.assertEqual(details.providerName, "azure-openai")
        self.assertEqual(details.inputTokens, 150)
        self.assertEqual(details.outputTokens, 75)
        self.assertEqual(details.finishReasons, ["stop"])
        self.assertEqual(details.responseId, "resp-123")

    def test_inference_scope_start_method(self):
        """Test InferenceScope.start() static method."""
        details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4",
            providerName="openai",
        )

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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
            execution_type=ExecutionType.EVENT_TO_AGENT,
            session_id="test-session-123",
        )

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details, request)

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
            execution_type=ExecutionType.AGENT_TO_AGENT,
            session_id="session-meta",
            source_metadata=SourceMetadata(name="Channel 1", description="Link to channel"),
        )

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details, request)

        if scope is not None:
            scope.dispose()

        finished_spans = self.span_exporter.get_finished_spans()
        self.assertTrue(finished_spans, "Expected at least one span to be created")

        span = finished_spans[-1]
        span_attributes = getattr(span, "attributes", {}) or {}

        self.assertIn(
            GEN_AI_EXECUTION_SOURCE_NAME_KEY,
            span_attributes,
            "Expected source name to be set on span",
        )
        self.assertEqual(
            span_attributes[GEN_AI_EXECUTION_SOURCE_NAME_KEY],
            request.source_metadata.name,
        )

        self.assertIn(
            GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
            span_attributes,
            "Expected source description to be set on span",
        )
        self.assertEqual(
            span_attributes[GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY],
            request.source_metadata.description,
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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

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

        scope = InferenceScope.start(details, self.agent_details, self.tenant_details)

        if scope is not None:
            # Test recording thought process
            thought_process = "Analyzing user input and generating appropriate response"
            scope.record_thought_process(thought_process)
            # Should not raise an exception
            self.assertTrue(hasattr(scope, "record_thought_process"))


if __name__ == "__main__":
    # Run pytest only on the current file
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

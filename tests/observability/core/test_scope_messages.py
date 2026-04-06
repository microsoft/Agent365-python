# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for structured message recording on InvokeAgentScope, InferenceScope, and OutputScope."""

import json
import os
import sys
import unittest
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core import (
    AgentDetails,
    InferenceCallDetails,
    InferenceOperationType,
    InferenceScope,
    InvokeAgentScope,
    InvokeAgentScopeDetails,
    Request,
    ServiceEndpoint,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.models.messages import (
    A365_MESSAGE_SCHEMA_VERSION,
    ChatMessage,
    FinishReason,
    InputMessages,
    MessageRole,
    OutputMessage,
    OutputMessages,
    ReasoningPart,
    TextPart,
)
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.opentelemetry_scope import OpenTelemetryScope
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class ScopeMessageTestBase(unittest.TestCase):
    """Shared setup for scope message tests."""

    @classmethod
    def setUpClass(cls):
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"
        configure(service_name="test-scope-messages", service_namespace="test")

        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
        )
        cls.invoke_scope_details = InvokeAgentScopeDetails(
            endpoint=ServiceEndpoint(hostname="example.com", port=443),
        )
        cls.inference_details = InferenceCallDetails(
            operationName=InferenceOperationType.CHAT,
            model="gpt-4o",
            providerName="openai",
        )

    def setUp(self):
        super().setUp()
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None
        configure(service_name="test-scope-messages", service_namespace="test")

        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def _get_last_span_attrs(self) -> dict:
        spans = self.span_exporter.get_finished_spans()
        self.assertTrue(spans, "Expected at least one span")
        return dict(getattr(spans[-1], "attributes", {}) or {})

    def _parse_messages(self, attr_value: str) -> dict:
        parsed = json.loads(attr_value)
        self.assertEqual(parsed["version"], A365_MESSAGE_SCHEMA_VERSION)
        return parsed


class TestInvokeAgentScopeMessages(ScopeMessageTestBase):
    """Tests for InvokeAgentScope message recording."""

    def test_record_input_messages_with_strings(self):
        """Plain string list should be auto-wrapped into versioned format."""
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)
        scope.record_input_messages(["What is GDPR?"])
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertEqual(parsed["messages"][0]["role"], "user")
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "What is GDPR?")

    def test_record_input_messages_with_structured(self):
        """Versioned InputMessages wrapper should be serialized as-is."""
        wrapper = InputMessages(
            messages=[
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    parts=[TextPart(content="You are a compliance assistant.")],
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    parts=[TextPart(content="What are data retention policies?")],
                ),
            ]
        )
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)
        scope.record_input_messages(wrapper)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 2)
        self.assertEqual(parsed["messages"][0]["role"], "system")
        self.assertEqual(parsed["messages"][1]["role"], "user")

    def test_record_output_messages_with_strings(self):
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)
        scope.record_output_messages(["GDPR requires data minimization."])
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["role"], "assistant")
        self.assertEqual(
            parsed["messages"][0]["parts"][0]["content"],
            "GDPR requires data minimization.",
        )

    def test_record_output_messages_with_structured(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ReasoningPart(content="Checking Article 5(1)(e)"),
                        TextPart(content="Based on GDPR..."),
                    ],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)
        scope.record_output_messages(wrapper)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        msg = parsed["messages"][0]
        self.assertEqual(msg["finish_reason"], "stop")
        self.assertEqual(len(msg["parts"]), 2)
        self.assertEqual(msg["parts"][0]["type"], "reasoning")
        self.assertEqual(msg["parts"][1]["type"], "text")

    def test_record_response_wraps_string(self):
        """record_response(str) should produce versioned output messages."""
        scope = InvokeAgentScope.start(Request(), self.invoke_scope_details, self.agent_details)
        scope.record_response("Simple response")
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Simple response")

    def test_request_content_string_auto_wrapped(self):
        """Request.content as plain string should be wrapped into versioned format."""
        request = Request(content="What is GDPR?")
        scope = InvokeAgentScope.start(request, self.invoke_scope_details, self.agent_details)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["role"], "user")
        self.assertIn("What is GDPR?", parsed["messages"][0]["parts"][0]["content"])

    def test_request_content_structured_input(self):
        """Request.content as InputMessages should be serialized directly."""
        wrapper = InputMessages(
            messages=[ChatMessage(role=MessageRole.USER, parts=[TextPart(content="Hello")])]
        )
        request = Request(content=wrapper)
        scope = InvokeAgentScope.start(request, self.invoke_scope_details, self.agent_details)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Hello")


class TestInferenceScopeMessages(ScopeMessageTestBase):
    """Tests for InferenceScope message recording."""

    def test_record_input_messages_with_strings(self):
        scope = InferenceScope.start(Request(), self.inference_details, self.agent_details)
        scope.record_input_messages(["Explain quantum computing"])
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["role"], "user")
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Explain quantum computing")

    def test_record_input_messages_with_structured(self):
        wrapper = InputMessages(
            messages=[
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    parts=[TextPart(content="You are helpful.")],
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    parts=[TextPart(content="Question")],
                ),
            ]
        )
        scope = InferenceScope.start(Request(), self.inference_details, self.agent_details)
        scope.record_input_messages(wrapper)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 2)

    def test_record_output_messages_with_strings(self):
        scope = InferenceScope.start(Request(), self.inference_details, self.agent_details)
        scope.record_output_messages(["Quantum computing uses qubits."])
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["role"], "assistant")

    def test_record_output_messages_with_structured(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Answer")],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        scope = InferenceScope.start(Request(), self.inference_details, self.agent_details)
        scope.record_output_messages(wrapper)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["finish_reason"], "stop")

    def test_request_content_string_auto_wrapped(self):
        request = Request(content="Test content")
        scope = InferenceScope.start(request, self.inference_details, self.agent_details)
        scope.dispose()

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Test content")


class TestOutputScopeMessages(ScopeMessageTestBase):
    """Tests for OutputScope structured message support."""

    def test_initial_string_messages_wrapped(self):
        """Response with plain strings should produce versioned output."""
        response = Response(messages=["First", "Second"])
        with OutputScope.start(Request(), response, self.agent_details):
            pass

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 2)
        self.assertEqual(parsed["messages"][0]["role"], "assistant")
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "First")
        self.assertEqual(parsed["messages"][1]["parts"][0]["content"], "Second")

    def test_initial_structured_messages(self):
        """Response with OutputMessages should be serialized directly."""
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Structured output")],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        response = Response(messages=wrapper)
        with OutputScope.start(Request(), response, self.agent_details):
            pass

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["finish_reason"], "stop")

    def test_record_overwrites_string_messages(self):
        """record_output_messages with strings overwrites previous messages."""
        response = Response(messages=["Initial"])
        with OutputScope.start(Request(), response, self.agent_details) as scope:
            scope.record_output_messages(["Replacement"])

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertNotIn("Initial", attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Replacement")

    def test_record_overwrites_with_structured(self):
        """record_output_messages with OutputMessages overwrites previous messages."""
        response = Response(messages=["Initial"])
        replacement = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Structured replacement")],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        with OutputScope.start(Request(), response, self.agent_details) as scope:
            scope.record_output_messages(replacement)

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertEqual(parsed["messages"][0]["finish_reason"], "stop")

    def test_record_overwrites_with_dict(self):
        """record_output_messages with dict sets tool result directly."""
        response = Response(messages=["Initial"])
        with OutputScope.start(Request(), response, self.agent_details) as scope:
            scope.record_output_messages({"result": "tool output"})

        attrs = self._get_last_span_attrs()
        parsed = json.loads(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(parsed["result"], "tool output")

    def test_no_record_keeps_initial(self):
        """If record_output_messages is not called, initial value remains."""
        response = Response(messages=["Only initial"])
        with OutputScope.start(Request(), response, self.agent_details):
            pass

        attrs = self._get_last_span_attrs()
        parsed = self._parse_messages(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Only initial")


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

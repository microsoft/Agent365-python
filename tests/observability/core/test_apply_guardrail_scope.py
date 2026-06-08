# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import unittest

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ApplyGuardrailScope,
    Channel,
    Request,
    configure,
    get_tracer_provider,
)
from microsoft_agents_a365.observability.core.config import _telemetry_manager
from microsoft_agents_a365.observability.core.constants import (
    APPLY_GUARDRAIL_OPERATION_NAME,
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GUARDIAN_ID_KEY,
    GUARDIAN_NAME_KEY,
    GUARDIAN_PROVIDER_NAME_KEY,
    GUARDIAN_VERSION_KEY,
    SECURITY_CONTENT_INPUT_HASH_KEY,
    SECURITY_CONTENT_INPUT_VALUE_KEY,
    SECURITY_CONTENT_MODIFIED_KEY,
    SECURITY_CONTENT_OUTPUT_VALUE_KEY,
    SECURITY_DECISION_REASON_KEY,
    SECURITY_DECISION_TYPE_KEY,
    SECURITY_EXTERNAL_EVENT_ID_KEY,
    SECURITY_FINDING_EVENT_NAME,
    SECURITY_POLICY_DECISION_TYPE_KEY,
    SECURITY_POLICY_ID_KEY,
    SECURITY_POLICY_NAME_KEY,
    SECURITY_POLICY_VERSION_KEY,
    SECURITY_RISK_CATEGORY_KEY,
    SECURITY_RISK_SCORE_KEY,
    SECURITY_RISK_SEVERITY_KEY,
    SECURITY_TARGET_TYPE_KEY,
)
from microsoft_agents_a365.observability.core.guardrail_decision_type import (
    GuardrailDecisionType,
)
from microsoft_agents_a365.observability.core.guardrail_details import GuardrailDetails
from microsoft_agents_a365.observability.core.guardrail_finding import GuardrailFinding
from microsoft_agents_a365.observability.core.guardrail_risk_severity import (
    GuardrailRiskSeverity,
)
from microsoft_agents_a365.observability.core.guardrail_target_type import (
    GuardrailTargetType,
)
from microsoft_agents_a365.observability.core.opentelemetry_scope import (
    OpenTelemetryScope,
)
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind


class TestApplyGuardrailScope(unittest.TestCase):
    """Unit tests for ApplyGuardrailScope."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        os.environ["ENABLE_A365_OBSERVABILITY"] = "true"
        configure(
            service_name="test-guardrail-service",
            service_namespace="test-namespace",
        )
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent",
        )

    def setUp(self):
        super().setUp()
        _telemetry_manager._tracer_provider = None
        _telemetry_manager._span_processors = {}
        OpenTelemetryScope._tracer = None

        configure(
            service_name="test-guardrail-service",
            service_namespace="test-namespace",
        )

        self.span_exporter = InMemorySpanExporter()
        tracer_provider = get_tracer_provider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.span_exporter))

    def tearDown(self):
        super().tearDown()
        self.span_exporter.clear()

    def _get_attributes(self, span):
        """Helper to get span attributes as a dict."""
        return dict(span.attributes) if span.attributes else {}

    def test_start_sets_required_attributes(self):
        """Test that Start sets required attributes."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.DENY,
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[GEN_AI_OPERATION_NAME_KEY], APPLY_GUARDRAIL_OPERATION_NAME)
        self.assertEqual(attrs[SECURITY_DECISION_TYPE_KEY], "deny")
        self.assertEqual(attrs[SECURITY_TARGET_TYPE_KEY], GuardrailTargetType.LLM_INPUT)

    def test_start_sets_guardian_attributes(self):
        """Test that guardian attributes are set when provided."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_OUTPUT,
            decision_type=GuardrailDecisionType.ALLOW,
            guardian_name="PII Filter",
            guardian_id="guard_abc123",
            guardian_provider_name="azure.ai.content_safety",
            guardian_version="2.1.0",
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[GUARDIAN_NAME_KEY], "PII Filter")
        self.assertEqual(attrs[GUARDIAN_ID_KEY], "guard_abc123")
        self.assertEqual(attrs[GUARDIAN_PROVIDER_NAME_KEY], "azure.ai.content_safety")
        self.assertEqual(attrs[GUARDIAN_VERSION_KEY], "2.1.0")

    def test_start_sets_policy_attributes(self):
        """Test that policy attributes are set when provided."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.TOOL_CALL,
            decision_type=GuardrailDecisionType.MODIFY,
            policy_id="policy_pii_v2",
            policy_name="PII Protection Policy",
            policy_version="1.0",
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[SECURITY_POLICY_ID_KEY], "policy_pii_v2")
        self.assertEqual(attrs[SECURITY_POLICY_NAME_KEY], "PII Protection Policy")
        self.assertEqual(attrs[SECURITY_POLICY_VERSION_KEY], "1.0")

    def test_start_sets_content_attributes(self):
        """Test that content attributes are set when provided."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
            content_input_hash="sha256:abc123",
            content_modified=True,
            external_event_id="ext-001",
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[SECURITY_CONTENT_INPUT_HASH_KEY], "sha256:abc123")
        self.assertEqual(attrs[SECURITY_CONTENT_MODIFIED_KEY], True)
        self.assertEqual(attrs[SECURITY_EXTERNAL_EVENT_ID_KEY], "ext-001")

    def test_start_builds_activity_name_with_guardian_name(self):
        """Test activity name includes guardian name when provided."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.DENY,
            guardian_name="Azure Content Safety",
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        self.assertEqual(spans[0].name, "apply_guardrail Azure Content Safety llm_input")

    def test_start_builds_activity_name_without_guardian_name(self):
        """Test activity name without guardian name."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.TOOL_CALL,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        self.assertEqual(spans[0].name, "apply_guardrail tool_call")

    def test_record_decision_updates_decision_type(self):
        """Test that RecordDecision updates the decision type."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        with ApplyGuardrailScope.start(details, self.agent_details) as scope:
            scope.record_decision(GuardrailDecisionType.DENY, "Content blocked")

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[SECURITY_DECISION_TYPE_KEY], "deny")
        self.assertEqual(attrs[SECURITY_DECISION_REASON_KEY], "Content blocked")

    def test_record_content_output_sets_output_value(self):
        """Test that RecordContentOutput sets the output value."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_OUTPUT,
            decision_type=GuardrailDecisionType.MODIFY,
        )

        with ApplyGuardrailScope.start(details, self.agent_details) as scope:
            scope.record_content_output("sanitized content")

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[SECURITY_CONTENT_OUTPUT_VALUE_KEY], "sanitized content")

    def test_record_finding_adds_event_with_attributes(self):
        """Test that RecordFinding adds an event with correct attributes."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.DENY,
        )

        finding = GuardrailFinding(
            risk_category="hate_speech",
            risk_severity=GuardrailRiskSeverity.HIGH,
            policy_decision_type="deny",
            policy_id="policy-abc",
            risk_score=0.95,
            risk_metadata=['{"category":"hate","confidence":0.95}'],
        )

        with ApplyGuardrailScope.start(details, self.agent_details) as scope:
            scope.record_finding(finding)

        spans = self.span_exporter.get_finished_spans()
        events = spans[0].events
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.name, SECURITY_FINDING_EVENT_NAME)

        event_attrs = dict(event.attributes)
        self.assertEqual(event_attrs[SECURITY_RISK_CATEGORY_KEY], "hate_speech")
        self.assertEqual(event_attrs[SECURITY_RISK_SEVERITY_KEY], GuardrailRiskSeverity.HIGH)
        self.assertEqual(event_attrs[SECURITY_POLICY_DECISION_TYPE_KEY], "deny")
        self.assertEqual(event_attrs[SECURITY_POLICY_ID_KEY], "policy-abc")
        self.assertEqual(event_attrs[SECURITY_RISK_SCORE_KEY], 0.95)

    def test_record_finding_multiple_findings(self):
        """Test that multiple findings can be recorded."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.DENY,
        )

        with ApplyGuardrailScope.start(details, self.agent_details) as scope:
            scope.record_finding(GuardrailFinding("hate_speech", GuardrailRiskSeverity.HIGH))
            scope.record_finding(GuardrailFinding("pii", GuardrailRiskSeverity.MEDIUM))

        spans = self.span_exporter.get_finished_spans()
        self.assertEqual(len(spans[0].events), 2)

    def test_record_finding_raises_on_none(self):
        """Test that RecordFinding raises on None."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        with self.assertRaises(ValueError):
            with ApplyGuardrailScope.start(details, self.agent_details) as scope:
                scope.record_finding(None)

    def test_start_sets_request_context(self):
        """Test that request context attributes are set when provided."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        request = Request(
            content="test input",
            conversation_id="conv-123",
            channel=Channel(name="msteams", link="https://test.link"),
        )

        with ApplyGuardrailScope.start(details, self.agent_details, request=request):
            pass

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        self.assertEqual(attrs[SECURITY_CONTENT_INPUT_VALUE_KEY], "test input")
        self.assertEqual(attrs[GEN_AI_CONVERSATION_ID_KEY], "conv-123")
        self.assertEqual(attrs[CHANNEL_NAME_KEY], "msteams")
        self.assertEqual(attrs[CHANNEL_LINK_KEY], "https://test.link")

    def test_span_kind_is_internal(self):
        """Test that the span kind defaults to INTERNAL."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        with ApplyGuardrailScope.start(details, self.agent_details):
            pass

        spans = self.span_exporter.get_finished_spans()
        self.assertEqual(spans[0].kind, SpanKind.INTERNAL)

    def test_all_decision_types(self):
        """Test all guardrail decision types are serialized correctly."""
        for decision_type in GuardrailDecisionType:
            self.span_exporter.clear()
            details = GuardrailDetails(
                target_type=GuardrailTargetType.LLM_INPUT,
                decision_type=decision_type,
            )
            with ApplyGuardrailScope.start(details, self.agent_details):
                pass

            spans = self.span_exporter.get_finished_spans()
            attrs = self._get_attributes(spans[0])
            self.assertEqual(attrs[SECURITY_DECISION_TYPE_KEY], decision_type.value)

    def test_request_content_serializes_structured_input(self):
        """Test that non-string request content is JSON-serialized."""
        details = GuardrailDetails(
            target_type=GuardrailTargetType.LLM_INPUT,
            decision_type=GuardrailDecisionType.ALLOW,
        )

        # Use a list of strings (InputMessagesParam allows list[str])
        request = Request(
            content=["hello", "world"],
            conversation_id="conv-456",
        )

        with ApplyGuardrailScope.start(details, self.agent_details, request=request):
            pass

        spans = self.span_exporter.get_finished_spans()
        attrs = self._get_attributes(spans[0])
        # Should be JSON-serialized since it's not a plain string
        self.assertEqual(attrs[SECURITY_CONTENT_INPUT_VALUE_KEY], '["hello", "world"]')


if __name__ == "__main__":
    unittest.main()

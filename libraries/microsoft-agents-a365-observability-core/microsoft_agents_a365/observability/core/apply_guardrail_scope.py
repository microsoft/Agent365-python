# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from opentelemetry.trace import SpanKind

from .agent_details import AgentDetails
from .constants import (
    APPLY_GUARDRAIL_OPERATION_NAME,
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GUARDIAN_ID_KEY,
    GUARDIAN_NAME_KEY,
    GUARDIAN_PROVIDER_NAME_KEY,
    GUARDIAN_VERSION_KEY,
    SECURITY_CONTENT_INPUT_HASH_KEY,
    SECURITY_CONTENT_INPUT_VALUE_KEY,
    SECURITY_CONTENT_MODIFIED_KEY,
    SECURITY_CONTENT_OUTPUT_VALUE_KEY,
    SECURITY_DECISION_CODE_KEY,
    SECURITY_DECISION_REASON_KEY,
    SECURITY_DECISION_TYPE_KEY,
    SECURITY_EXTERNAL_EVENT_ID_KEY,
    SECURITY_FINDING_EVENT_NAME,
    SECURITY_POLICY_DECISION_TYPE_KEY,
    SECURITY_POLICY_ID_KEY,
    SECURITY_POLICY_NAME_KEY,
    SECURITY_POLICY_VERSION_KEY,
    SECURITY_RISK_CATEGORY_KEY,
    SECURITY_RISK_METADATA_KEY,
    SECURITY_RISK_SCORE_KEY,
    SECURITY_RISK_SEVERITY_KEY,
    SECURITY_TARGET_ID_KEY,
    SECURITY_TARGET_TYPE_KEY,
)
from .guardrail_decision_type import GuardrailDecisionType
from .guardrail_details import GuardrailDetails
from .guardrail_finding import GuardrailFinding
from .models.user_details import UserDetails
from .opentelemetry_scope import OpenTelemetryScope
from .request import Request
from .span_details import SpanDetails
from .utils import safe_json_dumps


class ApplyGuardrailScope(OpenTelemetryScope):
    """Provides OpenTelemetry tracing scope for security guardrail evaluation operations.

    Describes a security guardian evaluation. Multiple guardian spans MAY exist under a
    single operation span if multiple guardians are chained.

    Guardian spans SHOULD be children of the operation span they are protecting
    (e.g., inference or execute_tool spans).
    """

    @staticmethod
    def start(
        details: GuardrailDetails,
        agent_details: AgentDetails,
        request: Request | None = None,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ) -> "ApplyGuardrailScope":
        """Creates and starts a new scope for guardrail evaluation tracing.

        Args:
            details: Details of the guardrail evaluation (target, decision, guardian
                info, policy).
            agent_details: Information about the agent being guarded.
            request: Optional request details for conversation context.
            user_details: Optional human user details.
            span_details: Optional span configuration (parent context, timing, kind,
                span links).

        Returns:
            A new ApplyGuardrailScope instance.
        """
        return ApplyGuardrailScope(details, agent_details, request, user_details, span_details)

    def __init__(
        self,
        details: GuardrailDetails,
        agent_details: AgentDetails,
        request: Request | None = None,
        user_details: UserDetails | None = None,
        span_details: SpanDetails | None = None,
    ):
        """Initialize the guardrail evaluation scope.

        Args:
            details: Details of the guardrail evaluation.
            agent_details: Information about the agent being guarded.
            request: Optional request details for conversation context.
            user_details: Optional human user details.
            span_details: Optional span configuration.
        """
        resolved_span_details = SpanDetails(
            span_kind=(
                span_details.span_kind
                if span_details and span_details.span_kind
                else SpanKind.INTERNAL
            ),
            parent_context=span_details.parent_context if span_details else None,
            start_time=span_details.start_time if span_details else None,
            end_time=span_details.end_time if span_details else None,
            span_links=span_details.span_links if span_details else None,
        )

        activity_name = self._build_activity_name(details)

        super().__init__(
            operation_name=APPLY_GUARDRAIL_OPERATION_NAME,
            activity_name=activity_name,
            agent_details=agent_details,
            span_details=resolved_span_details,
        )

        # Required attributes
        self.set_tag_maybe(SECURITY_DECISION_TYPE_KEY, details.decision_type.value)
        self.set_tag_maybe(SECURITY_TARGET_TYPE_KEY, details.target_type)

        # Guardian attributes
        self.set_tag_maybe(GUARDIAN_ID_KEY, details.guardian_id)
        self.set_tag_maybe(GUARDIAN_NAME_KEY, details.guardian_name)
        self.set_tag_maybe(GUARDIAN_PROVIDER_NAME_KEY, details.guardian_provider_name)
        self.set_tag_maybe(GUARDIAN_VERSION_KEY, details.guardian_version)

        # Target attributes
        self.set_tag_maybe(SECURITY_TARGET_ID_KEY, details.target_id)

        # Decision attributes
        self.set_tag_maybe(SECURITY_DECISION_REASON_KEY, details.decision_reason)
        self.set_tag_maybe(SECURITY_DECISION_CODE_KEY, details.decision_code)

        # Policy attributes
        self.set_tag_maybe(SECURITY_POLICY_ID_KEY, details.policy_id)
        self.set_tag_maybe(SECURITY_POLICY_NAME_KEY, details.policy_name)
        self.set_tag_maybe(SECURITY_POLICY_VERSION_KEY, details.policy_version)

        # Content attributes
        self.set_tag_maybe(SECURITY_CONTENT_INPUT_HASH_KEY, details.content_input_hash)
        if details.content_modified is not None:
            self.set_tag_maybe(SECURITY_CONTENT_MODIFIED_KEY, details.content_modified)

        # Correlation
        self.set_tag_maybe(SECURITY_EXTERNAL_EVENT_ID_KEY, details.external_event_id)

        # Request context
        if request is not None:
            content_value = self._serialize_content(request.content)
            self.set_tag_maybe(SECURITY_CONTENT_INPUT_VALUE_KEY, content_value)
            self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, request.conversation_id)
            if request.channel is not None:
                self.set_tag_maybe(CHANNEL_NAME_KEY, request.channel.name)
                self.set_tag_maybe(CHANNEL_LINK_KEY, request.channel.link)

    def record_decision(
        self, decision_type: GuardrailDecisionType, reason: str | None = None
    ) -> None:
        """Records an updated decision on the guardrail span.

        Use this when the guardrail decision is determined after span creation.

        Args:
            decision_type: The decision type made by the guardian.
            reason: Optional human-readable explanation for the decision.
        """
        self.set_tag_maybe(SECURITY_DECISION_TYPE_KEY, decision_type.value)
        self.set_tag_maybe(SECURITY_DECISION_REASON_KEY, reason)

    def record_content_output(self, output_value: str) -> None:
        """Records the output content value for the guardrail evaluation (opt-in).

        Args:
            output_value: The output content after guardrail processing.
        """
        self.set_tag_maybe(SECURITY_CONTENT_OUTPUT_VALUE_KEY, output_value)

    def record_finding(self, finding: GuardrailFinding) -> None:
        """Records a security finding event on the current span.

        Multiple findings may be recorded per guardrail evaluation.

        Args:
            finding: The security finding to record.

        Raises:
            ValueError: When finding is None.
        """
        if finding is None:
            raise ValueError("finding must not be None")

        if self._span is None or not self._is_telemetry_enabled():
            return

        attributes: dict[str, str | float | list[str]] = {
            SECURITY_RISK_CATEGORY_KEY: finding.risk_category,
            SECURITY_RISK_SEVERITY_KEY: finding.risk_severity,
        }

        if finding.policy_decision_type is not None:
            attributes[SECURITY_POLICY_DECISION_TYPE_KEY] = finding.policy_decision_type

        if finding.policy_id is not None:
            attributes[SECURITY_POLICY_ID_KEY] = finding.policy_id

        if finding.policy_name is not None:
            attributes[SECURITY_POLICY_NAME_KEY] = finding.policy_name

        if finding.policy_version is not None:
            attributes[SECURITY_POLICY_VERSION_KEY] = finding.policy_version

        if finding.risk_score is not None:
            attributes[SECURITY_RISK_SCORE_KEY] = finding.risk_score

        if finding.risk_metadata is not None:
            attributes[SECURITY_RISK_METADATA_KEY] = finding.risk_metadata

        self._span.add_event(SECURITY_FINDING_EVENT_NAME, attributes=attributes)

    @staticmethod
    def _build_activity_name(details: GuardrailDetails) -> str:
        """Build the display name for the span."""
        if details.guardian_name:
            return f"{APPLY_GUARDRAIL_OPERATION_NAME} {details.guardian_name} {details.target_type}"
        return f"{APPLY_GUARDRAIL_OPERATION_NAME} {details.target_type}"

    @staticmethod
    def _serialize_content(content: object) -> str | None:
        """Serialize request content to a string suitable for an OTel attribute.

        OTel attributes only accept primitive values or sequences of primitives.
        If content is already a string it is returned as-is; otherwise it is
        JSON-serialized so that structured InputMessages objects are captured.
        """
        if content is None:
            return None
        if isinstance(content, str):
            return content
        return safe_json_dumps(content)

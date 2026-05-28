# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass

from .guardrail_decision_type import GuardrailDecisionType


@dataclass(frozen=True)
class GuardrailDetails:
    """Details of a guardrail evaluation for security operations tracing.

    Args:
        target_type: The type of content or action the guardrail is applied to (required).
            See GuardrailTargetType for well-known values.
        decision_type: The decision made by the guardian (required).
        guardian_name: Human-readable name of the guardian.
        guardian_id: Unique identifier of the guardian.
        guardian_provider_name: Provider of the guardian service
            (e.g., azure.ai.content_safety).
        guardian_version: Version of the guardian.
        target_id: Identifier of the target being guarded.
        decision_reason: Human-readable explanation for the decision.
        decision_code: Machine-readable decision code.
        policy_id: Identifier of the policy that triggered the decision.
        policy_name: Human-readable name of the policy.
        policy_version: Version of the policy.
        content_input_hash: Hash of the input content for forensic correlation.
        content_modified: Whether content was modified by the guardrail.
        external_event_id: External correlation identifier for SIEM systems.
    """

    target_type: str
    decision_type: GuardrailDecisionType
    guardian_name: str | None = None
    guardian_id: str | None = None
    guardian_provider_name: str | None = None
    guardian_version: str | None = None
    target_id: str | None = None
    decision_reason: str | None = None
    decision_code: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None
    policy_version: str | None = None
    content_input_hash: str | None = None
    content_modified: bool | None = None
    external_event_id: str | None = None

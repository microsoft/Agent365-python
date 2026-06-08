# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailFinding:
    """Represents a single security finding detected during guardian evaluation.

    Multiple findings may be emitted for a single guardrail span.

    Args:
        risk_category: The category of security risk detected (required).
            Common values: prompt_injection, sensitive_info_disclosure, jailbreak,
            toxicity, pii.
        risk_severity: The severity level of the detected risk (required).
            See GuardrailRiskSeverity for well-known values.
        policy_decision_type: The decision type for this specific policy finding.
        policy_id: Identifier of the policy that triggered the finding.
        policy_name: Human-readable name of the triggered policy.
        policy_version: Version of the policy.
        risk_score: Numeric risk/confidence score (0.0 to 1.0).
        risk_metadata: Non-content metadata about the detected risk
            (MUST NOT contain PII).
    """

    risk_category: str
    risk_severity: str
    policy_decision_type: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None
    policy_version: str | None = None
    risk_score: float | None = None
    risk_metadata: list[str] | None = None

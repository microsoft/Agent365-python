# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


class GuardrailRiskSeverity:
    """Well-known severity levels for security risks detected by guardrails."""

    NONE = "none"
    """No risk detected."""

    LOW = "low"
    """Low severity risk."""

    MEDIUM = "medium"
    """Medium severity risk."""

    HIGH = "high"
    """High severity risk."""

    CRITICAL = "critical"
    """Critical severity risk requiring immediate action."""

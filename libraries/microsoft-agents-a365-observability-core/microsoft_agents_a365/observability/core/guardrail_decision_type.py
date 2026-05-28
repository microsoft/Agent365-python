# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class GuardrailDecisionType(Enum):
    """The decision made by a security guardian during guardrail evaluation."""

    ALLOW = "allow"
    """Content or action is allowed to proceed."""

    AUDIT = "audit"
    """Content or action is logged for review but allowed to proceed."""

    DENY = "deny"
    """Content or action is denied/blocked."""

    MODIFY = "modify"
    """Content was modified (e.g., redacted, sanitized, rewritten)."""

    WARN = "warn"
    """Content or action triggered a warning but is allowed to proceed."""

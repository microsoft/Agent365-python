# Copyright (c) Microsoft. All rights reserved.

import json
import logging
import os
from collections.abc import Sequence
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanKind, StatusCode

from ..constants import (
    ENABLE_A365_OBSERVABILITY_EXPORTER,
    GEN_AI_AGENT_ID_KEY,
    TENANT_ID_KEY,
)

logger = logging.getLogger(__name__)

# Maximum allowed span size in bytes (250KB)
MAX_SPAN_SIZE_BYTES = 250 * 1024


def hex_trace_id(value: int) -> str:
    # 128-bit -> 32 hex chars
    return f"{value:032x}"


def hex_span_id(value: int) -> str:
    # 64-bit -> 16 hex chars
    return f"{value:016x}"


def as_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s.strip() else None


def kind_name(kind: SpanKind) -> str:
    # Return span kind name (enum name or numeric)
    try:
        return kind.name  # Enum in otel 1.27+
    except Exception:
        return str(kind)


def status_name(code: StatusCode) -> str:
    try:
        return code.name
    except Exception:
        return str(code)


def truncate_span(span_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Truncate span attributes if the serialized span exceeds MAX_SPAN_SIZE_BYTES.

    Args:
        span_dict: The span dictionary to potentially truncate

    Returns:
        The potentially truncated span dictionary
    """
    try:
        # Serialize the span to check its size
        serialized = json.dumps(span_dict, separators=(",", ":"))
        current_size = len(serialized.encode("utf-8"))

        if current_size <= MAX_SPAN_SIZE_BYTES:
            return span_dict

        logger.warning(
            f"Span size ({current_size} bytes) exceeds limit ({MAX_SPAN_SIZE_BYTES} bytes). "
            "Truncating large payload attributes."
        )

        # Create a deep copy to modify (shallow copy would still reference original attributes)
        truncated_span = span_dict.copy()
        if "attributes" in truncated_span:
            truncated_span["attributes"] = truncated_span["attributes"].copy()
        attributes = truncated_span.get("attributes", {})

        # Track what was truncated for logging
        truncated_keys = []

        # Sort attributes by size (largest first) and truncate until size is acceptable
        if attributes:
            # Calculate size of each attribute value when serialized
            attr_sizes = []
            for key, value in attributes.items():
                try:
                    value_size = len(json.dumps(value, separators=(",", ":")).encode("utf-8"))
                    attr_sizes.append((key, value_size))
                except Exception:
                    # If we can't serialize the value, assume it's small
                    attr_sizes.append((key, 0))

            # Sort by size (descending - largest first)
            attr_sizes.sort(key=lambda x: x[1], reverse=True)

            # Truncate largest attributes first until size is acceptable
            for key, _ in attr_sizes:
                if key in attributes:
                    attributes[key] = "TRUNCATED"
                    truncated_keys.append(key)

                    # Check size after truncation
                    serialized = json.dumps(truncated_span, separators=(",", ":"))
                    current_size = len(serialized.encode("utf-8"))

                    if current_size <= MAX_SPAN_SIZE_BYTES:
                        break

        if truncated_keys:
            logger.info(f"Truncated attributes: {', '.join(truncated_keys)}")

        return truncated_span

    except Exception as e:
        logger.error(f"Error during span truncation: {e}")
        return span_dict


def partition_by_identity(
    spans: Sequence[ReadableSpan],
) -> dict[tuple[str, str], list[ReadableSpan]]:
    """
    Extract (tenantId, agentId). Prefer attributes; if you also stamp baggage
    into attributes via a processor, they'll be here already.
    """
    groups: dict[tuple[str, str], list[ReadableSpan]] = {}
    for sp in spans:
        attrs = sp.attributes or {}
        tenant = as_str(attrs.get(TENANT_ID_KEY))
        agent = as_str(attrs.get(GEN_AI_AGENT_ID_KEY))
        if not tenant or not agent:
            continue
        key = (tenant, agent)
        groups.setdefault(key, []).append(sp)
    return groups


def get_validated_domain_override() -> str | None:
    """
    Get and validate the domain override from environment variable.

    Returns:
        The validated domain override, or None if not set or invalid.
    """
    domain_override = os.getenv("A365_OBSERVABILITY_DOMAIN_OVERRIDE", "").strip()
    if not domain_override:
        return None

    # Basic validation: ensure domain doesn't contain protocol or path separators
    if "://" in domain_override or "/" in domain_override:
        logger.warning(
            f"Invalid domain override '{domain_override}': "
            "domain should not contain protocol (://) or path separators (/)"
        )
        return None

    return domain_override


def is_agent365_exporter_enabled() -> bool:
    """Check if Agent 365 exporter is enabled."""
    # Check environment variable
    enable_exporter = os.getenv(ENABLE_A365_OBSERVABILITY_EXPORTER, "").lower()
    return (enable_exporter) in ("true", "1", "yes", "on")

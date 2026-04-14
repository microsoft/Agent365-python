# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

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

    # Validate that it's a valid URL
    try:
        parsed = urlparse(domain_override)

        # If scheme is present and looks like a protocol (contains //)
        # Note: We check for "://" because urlparse treats "example.com:8080" as having
        # scheme="example.com", but this is actually a domain with port, not a protocol.
        if parsed.scheme and "://" in domain_override:
            # Validate it's http or https
            if parsed.scheme not in ("http", "https"):
                logger.warning(
                    f"Invalid domain override '{domain_override}': "
                    f"scheme must be http or https, got '{parsed.scheme}'"
                )
                return None
            # Must have a netloc (hostname) when scheme is present
            if not parsed.netloc:
                logger.warning(f"Invalid domain override '{domain_override}': missing hostname")
                return None
        else:
            # If no scheme with ://, it should be a domain with optional port (no path)
            # Note: domain can contain : for port (e.g., example.com:8080)
            # Reject malformed URLs like "http:8080" that look like protocols but aren't
            if domain_override.startswith(("http:", "https:")) and "://" not in domain_override:
                logger.warning(
                    f"Invalid domain override '{domain_override}': "
                    "malformed URL - protocol requires '://'"
                )
                return None
            if "/" in domain_override:
                logger.warning(
                    f"Invalid domain override '{domain_override}': "
                    "domain without protocol should not contain path separators (/)"
                )
                return None
    except Exception as e:
        logger.warning(f"Invalid domain override '{domain_override}': {e}")
        return None

    # Warn when using insecure HTTP — telemetry data and bearer tokens may be exposed
    if domain_override.lower().startswith("http://"):
        logger.warning(
            "Domain override uses insecure HTTP. Telemetry data (including "
            "bearer tokens) will be transmitted in cleartext."
        )

    return domain_override


def build_export_url(
    endpoint: str, agent_id: str, tenant_id: str, use_s2s_endpoint: bool = False
) -> str:
    """Construct the full export URL from endpoint and agent ID.

    Args:
        endpoint: Base endpoint URL or domain.
        agent_id: The agent identifier to include in the URL path.
        tenant_id: The tenant identifier to include in the URL path.
        use_s2s_endpoint: Whether to use the S2S endpoint path format.

    Returns:
        The fully constructed export URL with path and query parameters.
    """
    endpoint_path = (
        f"/observabilityService/tenants/{tenant_id}/otlp/agents/{agent_id}/traces"
        if use_s2s_endpoint
        else f"/observability/tenants/{tenant_id}/otlp/agents/{agent_id}/traces"
    )

    parsed = urlparse(endpoint)
    if parsed.scheme and "://" in endpoint:
        return f"{endpoint}{endpoint_path}?api-version=1"
    return f"https://{endpoint}{endpoint_path}?api-version=1"


def parse_retry_after(headers: dict[str, str]) -> float | None:
    """Parse the ``Retry-After`` header value.

    Only numeric (seconds) values are supported.  HTTP-date values
    (e.g. ``Wed, 21 Oct 2025 07:28:00 GMT``) are intentionally ignored
    and treated as absent, falling back to exponential backoff.

    Args:
        headers: Response headers mapping.

    Returns:
        The number of seconds to wait, or ``None`` if the header is
        absent, non-numeric, or otherwise invalid.
    """
    retry_after = headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        return float(retry_after)
    except (ValueError, TypeError):
        # Intentionally ignore HTTP-date formatted Retry-After values;
        # callers should fall back to exponential backoff.
        return None


def is_agent365_exporter_enabled() -> bool:
    """Check if Agent 365 exporter is enabled."""
    # Check environment variable
    enable_exporter = os.getenv(ENABLE_A365_OBSERVABILITY_EXPORTER, "").lower()
    return (enable_exporter) in ("true", "1", "yes", "on")

# Copyright (c) Microsoft. All rights reserved.

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


def is_agent365_exporter_enabled() -> bool:
    """Check if agent365 exporter is enabled."""
    # Check environment variable
    enable_exporter = os.getenv(ENABLE_A365_OBSERVABILITY_EXPORTER, "").lower()
    return (enable_exporter) in ("true", "1", "yes", "on")

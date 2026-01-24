# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Span processor for copying OpenTelemetry baggage entries onto spans.

This implementation assumes `opentelemetry.baggage.get_all` is available with the
signature `get_all(context: Context | None) -> Mapping[str, object]`.

For every new span:
  * Retrieve the current (or parent) context
  * Obtain all baggage entries via `baggage.get_all`
  * For each (key, value) pair with a truthy value not already present as a span
    attribute, add it via `span.set_attribute`
  * Never overwrites existing attributes
"""

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import SpanProcessor as BaseSpanProcessor

from ..constants import GEN_AI_OPERATION_NAME_KEY, INVOKE_AGENT_OPERATION_NAME, OPERATION_SOURCE_KEY
from ..models.operation_source import OperationSource
from .util import COMMON_ATTRIBUTES, INVOKE_AGENT_ATTRIBUTES


class SpanProcessor(BaseSpanProcessor):
    """Span processor that propagates every baggage key/value to span attributes."""

    def __init__(self):
        super().__init__()

    def on_start(self, span, parent_context=None):
        ctx = parent_context or context.get_current()
        if ctx is None:
            return super().on_start(span, parent_context)

        try:
            existing = getattr(span, "attributes", {}) or {}
        except Exception:
            existing = {}

        try:
            baggage_map = baggage.get_all(ctx) or {}
        except Exception:
            baggage_map = {}

        # Set operation source - coalesce baggage value with SDK default
        if OPERATION_SOURCE_KEY not in existing:
            operation_source = baggage_map.get(OPERATION_SOURCE_KEY) or OperationSource.SDK.value
            try:
                span.set_attribute(OPERATION_SOURCE_KEY, operation_source)
            except Exception:
                pass

        operation_name = existing.get(GEN_AI_OPERATION_NAME_KEY)
        is_invoke_agent = False
        if operation_name == INVOKE_AGENT_OPERATION_NAME:
            is_invoke_agent = True
        elif isinstance(getattr(span, "name", None), str) and span.name.startswith(
            INVOKE_AGENT_OPERATION_NAME
        ):
            is_invoke_agent = True

        # Build target key set (avoid duplicates).
        target_keys = list(COMMON_ATTRIBUTES)
        if is_invoke_agent:
            # Add invoke-agent-only attributes
            for k in INVOKE_AGENT_ATTRIBUTES:
                if k not in target_keys:
                    target_keys.append(k)

        for key in target_keys:
            if key in existing:
                continue
            value = baggage_map.get(key)
            if not value:
                continue
            try:
                span.set_attribute(key, value)
            except Exception:
                continue

        return super().on_start(span, parent_context)

    def on_end(self, span):
        super().on_end(span)

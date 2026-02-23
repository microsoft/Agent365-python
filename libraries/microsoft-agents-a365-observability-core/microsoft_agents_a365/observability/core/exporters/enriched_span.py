# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Enriched ReadableSpan wrapper for adding attributes to immutable spans."""

import json
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.util import types


class EnrichedReadableSpan(ReadableSpan):
    """
    Wrapper to add attributes to an immutable ReadableSpan.

    Since ReadableSpan is immutable after a span ends, this wrapper allows
    extensions to add additional attributes before export without modifying
    the original span.
    """

    def __init__(self, span: ReadableSpan, extra_attributes: dict):
        """
        Initialize the enriched span wrapper.

        Args:
            span: The original ReadableSpan to wrap.
            extra_attributes: Additional attributes to merge with the original.
        """
        self._span = span
        self._extra_attributes = extra_attributes

    @property
    def attributes(self) -> types.Attributes:
        """Return merged attributes from original span and extra attributes."""
        original = dict(self._span.attributes or {})
        original.update(self._extra_attributes)
        return original

    @property
    def name(self):
        """Return the span name."""
        return self._span.name

    @property
    def context(self):
        """Return the span context."""
        return self._span.context

    @property
    def parent(self):
        """Return the parent span context."""
        return self._span.parent

    @property
    def start_time(self):
        """Return the span start time."""
        return self._span.start_time

    @property
    def end_time(self):
        """Return the span end time."""
        return self._span.end_time

    @property
    def status(self):
        """Return the span status."""
        return self._span.status

    @property
    def kind(self):
        """Return the span kind."""
        return self._span.kind

    @property
    def events(self):
        """Return the span events."""
        return self._span.events

    @property
    def links(self):
        """Return the span links."""
        return self._span.links

    @property
    def resource(self):
        """Return the span resource."""
        return self._span.resource

    @property
    def instrumentation_scope(self):
        """Return the instrumentation scope."""
        return self._span.instrumentation_scope

    def to_json(self, indent: int | None = 4) -> str:
        """
        Convert span to JSON string with enriched attributes.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string representation of the span.
        """
        # Build the JSON dict manually to include enriched attributes
        return json.dumps(
            {
                "name": self.name,
                "context": {
                    "trace_id": f"0x{self.context.trace_id:032x}",
                    "span_id": f"0x{self.context.span_id:016x}",
                    "trace_state": str(self.context.trace_state),
                }
                if self.context
                else None,
                "kind": str(self.kind),
                "parent_id": f"0x{self.parent.span_id:016x}" if self.parent else None,
                "start_time": self._format_time(self.start_time),
                "end_time": self._format_time(self.end_time),
                "status": {
                    "status_code": str(self.status.status_code),
                    "description": self.status.description,
                }
                if self.status
                else None,
                "attributes": dict(self.attributes) if self.attributes else None,
                "events": [self._format_event(e) for e in self.events] if self.events else None,
                "links": [self._format_link(lnk) for lnk in self.links] if self.links else None,
                "resource": dict(self.resource.attributes) if self.resource else None,
            },
            indent=indent,
        )

    def _format_time(self, time_ns: int | None) -> str | None:
        """Format nanosecond timestamp to ISO string."""
        if time_ns is None:
            return None
        from datetime import datetime, timezone

        return datetime.fromtimestamp(time_ns / 1e9, tz=timezone.utc).isoformat()

    def _format_event(self, event: Any) -> dict:
        """Format a span event."""
        return {
            "name": event.name,
            "timestamp": self._format_time(event.timestamp),
            "attributes": dict(event.attributes) if event.attributes else None,
        }

    def _format_link(self, link: Any) -> dict:
        """Format a span link."""
        return {
            "context": {
                "trace_id": f"0x{link.context.trace_id:032x}",
                "span_id": f"0x{link.context.span_id:016x}",
            }
            if link.context
            else None,
            "attributes": dict(link.attributes) if link.attributes else None,
        }

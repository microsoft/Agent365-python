# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Base class for OpenTelemetry tracing scopes.

import logging
import os
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

from opentelemetry import baggage, context, trace
from opentelemetry.trace import (
    Span,
    SpanKind,
    Status,
    StatusCode,
    Tracer,
    set_span_in_context,
)

from .constants import (
    ENABLE_A365_OBSERVABILITY,
    ENABLE_OBSERVABILITY,
    ERROR_TYPE_KEY,
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_BLUEPRINT_ID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_AGENT_PLATFORM_ID_KEY,
    GEN_AI_AGENT_UPN_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_ICON_URI_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_PROVIDER_NAME_KEY,
    SOURCE_NAME,
    TELEMETRY_SDK_LANGUAGE_KEY,
    TELEMETRY_SDK_LANGUAGE_VALUE,
    TELEMETRY_SDK_NAME_KEY,
    TELEMETRY_SDK_NAME_VALUE,
    TELEMETRY_SDK_VERSION_KEY,
    TENANT_ID_KEY,
)
from .utils import get_sdk_version, parse_parent_id_to_context

if TYPE_CHECKING:
    from .agent_details import AgentDetails
    from .tenant_details import TenantDetails

# Create logger for this module - inherits from 'microsoft_agents_a365.observability.core'
logger = logging.getLogger(__name__)


class OpenTelemetryScope:
    """Base class for OpenTelemetry tracing scopes in the SDK."""

    _tracer: Tracer | None = None
    _tracer_lock = Lock()

    @classmethod
    def _get_tracer(cls) -> Tracer:
        """Get the tracer instance, creating it if necessary."""
        if cls._tracer is None:
            with cls._tracer_lock:
                if cls._tracer is None:
                    cls._tracer = trace.get_tracer(SOURCE_NAME)
        return cls._tracer

    @classmethod
    def _is_telemetry_enabled(cls) -> bool:
        """Check if telemetry is enabled."""
        # Check environment variable
        env_value = os.getenv(ENABLE_OBSERVABILITY, "").lower()
        enable_observability = os.getenv(ENABLE_A365_OBSERVABILITY, "").lower()
        return (env_value or enable_observability) in ("true", "1", "yes", "on")

    @staticmethod
    def _datetime_to_ns(dt: datetime | None) -> int | None:
        """Convert a datetime to nanoseconds since epoch.

        Args:
            dt: Python datetime object, or None

        Returns:
            Nanoseconds since epoch, or None if input is None
        """
        if dt is None:
            return None
        return int(dt.timestamp() * 1_000_000_000)

    def __init__(
        self,
        kind: str,
        operation_name: str,
        activity_name: str,
        agent_details: "AgentDetails | None" = None,
        tenant_details: "TenantDetails | None" = None,
        parent_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        """Initialize the OpenTelemetry scope.

        Args:
            kind: The kind of activity (Client, Server, Internal, etc.)
            operation_name: The name of the operation being traced
            activity_name: The name of the activity for display purposes
            agent_details: Optional agent details
            tenant_details: Optional tenant details
            parent_id: Optional parent Activity ID used to link this span to an upstream
                operation
            start_time: Optional explicit start time as a datetime object.
                Useful when recording an operation after it has already completed.
            end_time: Optional explicit end time as a datetime object.
                When provided, the span will use this timestamp when disposed
                instead of the current wall-clock time.
        """
        self._span: Span | None = None
        self._custom_start_time: datetime | None = start_time
        self._custom_end_time: datetime | None = end_time
        self._has_ended = False
        self._error_type: str | None = None
        self._exception: Exception | None = None
        self._context_token = None

        if self._is_telemetry_enabled():
            tracer = self._get_tracer()

            # Map string kind to SpanKind enum
            activity_kind = SpanKind.INTERNAL
            if kind.lower() == "client":
                activity_kind = SpanKind.CLIENT
            elif kind.lower() == "server":
                activity_kind = SpanKind.SERVER
            elif kind.lower() == "producer":
                activity_kind = SpanKind.PRODUCER
            elif kind.lower() == "consumer":
                activity_kind = SpanKind.CONSUMER

            # Get context for parent relationship
            # If parent_id is provided, parse it and use it as the parent context
            # Otherwise, use the current context
            parent_context = parse_parent_id_to_context(parent_id)
            span_context = parent_context if parent_context else context.get_current()

            # Convert custom start time to OTel-compatible format (nanoseconds since epoch)
            otel_start_time = self._datetime_to_ns(start_time)

            self._span = tracer.start_span(
                activity_name,
                kind=activity_kind,
                context=span_context,
                start_time=otel_start_time,
            )

            # Log span creation
            if self._span:
                span_id = f"{self._span.context.span_id:016x}" if self._span.context else "unknown"
                logger.info(f"Span started: '{activity_name}' ({span_id})")
            else:
                logger.error(f"Failed to create span: '{activity_name}' - tracer returned None")

            # Set common tags
            if self._span:
                self._span.set_attribute(GEN_AI_OPERATION_NAME_KEY, operation_name)

                # Set telemetry SDK attributes
                self._span.set_attribute(TELEMETRY_SDK_NAME_KEY, TELEMETRY_SDK_NAME_VALUE)
                self._span.set_attribute(TELEMETRY_SDK_LANGUAGE_KEY, TELEMETRY_SDK_LANGUAGE_VALUE)
                self._span.set_attribute(TELEMETRY_SDK_VERSION_KEY, get_sdk_version())

                # Set agent details if provided
                if agent_details:
                    self.set_tag_maybe(GEN_AI_AGENT_ID_KEY, agent_details.agent_id)
                    self.set_tag_maybe(GEN_AI_AGENT_NAME_KEY, agent_details.agent_name)
                    self.set_tag_maybe(
                        GEN_AI_AGENT_DESCRIPTION_KEY, agent_details.agent_description
                    )
                    self.set_tag_maybe(GEN_AI_AGENT_AUID_KEY, agent_details.agent_auid)
                    self.set_tag_maybe(GEN_AI_AGENT_UPN_KEY, agent_details.agent_upn)
                    self.set_tag_maybe(
                        GEN_AI_AGENT_BLUEPRINT_ID_KEY, agent_details.agent_blueprint_id
                    )
                    self.set_tag_maybe(
                        GEN_AI_AGENT_PLATFORM_ID_KEY, agent_details.agent_platform_id
                    )
                    self.set_tag_maybe(TENANT_ID_KEY, agent_details.tenant_id)
                    self.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, agent_details.conversation_id)
                    self.set_tag_maybe(GEN_AI_ICON_URI_KEY, agent_details.icon_uri)
                    # Set provider name dynamically from agent details
                    self.set_tag_maybe(GEN_AI_PROVIDER_NAME_KEY, agent_details.provider_name)

                # Set tenant details if provided
                if tenant_details:
                    self.set_tag_maybe(TENANT_ID_KEY, str(tenant_details.tenant_id))

    def record_error(self, exception: Exception) -> None:
        """Record an error in the span.

        Args:
            exception: The exception that occurred
        """
        if self._span and self._is_telemetry_enabled():
            self._error_type = type(exception).__name__
            self._exception = exception
            self._span.set_attribute(ERROR_TYPE_KEY, self._error_type)
            self._span.record_exception(exception)
            self._span.set_status(Status(StatusCode.ERROR, str(exception)))

    def record_response(self, response: str) -> None:
        """Record an response in the span.

        Args:
            response: The response content to record
        """
        if self._span and self._is_telemetry_enabled():
            self._span.set_attribute(GEN_AI_OUTPUT_MESSAGES_KEY, response)

    def record_cancellation(self) -> None:
        """Record task cancellation."""
        if self._span and self._is_telemetry_enabled():
            self._error_type = "TaskCanceledException"
            self._span.set_attribute(ERROR_TYPE_KEY, self._error_type)
            self._span.set_status(Status(StatusCode.ERROR, "Task was cancelled"))

    def set_tag_maybe(self, name: str, value: Any) -> None:
        """Set a tag on the span if the value is not None.

        Args:
            name: The name of the tag
            value: The value to set (will be skipped if None)
        """
        if value is not None and self._span and self._is_telemetry_enabled():
            self._span.set_attribute(name, value)

    def add_baggage(self, key: str, value: str) -> None:
        """Add baggage to the current context.

        Args:
            key: The baggage key
            value: The baggage value
        """
        # Set baggage in the current context
        if self._is_telemetry_enabled():
            # Set baggage on the current context
            # This will be inherited by child spans created within this context
            baggage_context = baggage.set_baggage(key, value)
            # The context needs to be made current for child spans to inherit the baggage
            context.attach(baggage_context)

    def record_attributes(self, attributes: dict[str, Any] | list[tuple[str, Any]]) -> None:
        """Record multiple attribute key/value pairs for telemetry tracking.

        This method allows setting multiple custom attributes on the span at once.

        Args:
            attributes: Dictionary or list of tuples containing attribute key-value pairs.
                       Keys that are None or empty will be skipped.
        """
        if not self._is_telemetry_enabled() or self._span is None:
            return

        # Handle both dict and list of tuples
        items = attributes.items() if isinstance(attributes, dict) else attributes

        for key, value in items:
            if key and key.strip():
                self._span.set_attribute(key, value)

    def set_end_time(self, end_time: datetime) -> None:
        """Set a custom end time for the scope.

        When set, dispose() will pass this value to span.end() instead of using
        the current wall-clock time. This is useful when the actual end time of
        the operation is known before the scope is disposed.

        Args:
            end_time: The end time as a datetime object.
        """
        self._custom_end_time = end_time

    def _end(self) -> None:
        """End the span and record metrics."""
        if self._span and self._is_telemetry_enabled() and not self._has_ended:
            self._has_ended = True
            span_id = f"{self._span.context.span_id:016x}" if self._span.context else "unknown"
            logger.info(f"Span ended: '{self._span.name}' ({span_id})")

            # Convert custom end time to OTel-compatible format (nanoseconds since epoch)
            otel_end_time = self._datetime_to_ns(self._custom_end_time)
            if otel_end_time is not None:
                self._span.end(end_time=otel_end_time)
            else:
                self._span.end()

    def __enter__(self):
        """Enter the context manager and make span active."""
        if self._span and self._is_telemetry_enabled():
            # Make this span the active span in the current context
            new_context = set_span_in_context(self._span)
            self._context_token = context.attach(new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and restore previous context."""
        try:
            if exc_type is not None and exc_val is not None:
                self.record_error(exc_val)
        finally:
            # Restore previous context
            if self._context_token is not None:
                context.detach(self._context_token)
            self._end()

    def dispose(self) -> None:
        """Dispose the scope and finalize telemetry data collection."""
        self._end()

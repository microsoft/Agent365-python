# Copyright (c) Microsoft. All rights reserved.

import logging
import threading
from collections.abc import Callable
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_NAMESPACE, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from .exporters.agent365_exporter import Agent365Exporter
from .exporters.utils import is_agent365_exporter_enabled
from .trace_processor.span_processor import SpanProcessor

DEFAULT_LOGGER_NAME = __name__


class TelemetryManager:
    """
    Thread-safe singleton manager for telemetry operations.

    This class encapsulates all telemetry state and operations, providing
    a clean interface for configuration, flushing, and shutdown without
    relying on global variables.
    """

    _instance: Optional["TelemetryManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TelemetryManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not getattr(self, "_initialized", False):
            self._tracer_provider: TracerProvider | None = None
            self._span_processors: dict[str, Any] = {}
            self._logger = logging.getLogger(__name__)
            self._initialized = True

    def configure(
        self,
        service_name: str,
        service_namespace: str,
        logger_name: str = DEFAULT_LOGGER_NAME,
        token_resolver: Callable[[str, str], str | None] | None = None,
        cluster_category: str = "prod",
        **kwargs: Any,
    ) -> bool:
        """
        Configure telemetry.

        :param service_name: The name of the service.
        :param service_namespace: The namespace of the service.
        :param logger_name: The name of the logger to collect telemetry from.
        :param token_resolver: Callable that returns an auth token for a given agent + tenant.
        :param cluster_category: Environment / cluster category (e.g., "preprod", "prod").
        :return: True if configuration succeeded, False otherwise.
        """
        try:
            with self._lock:
                return self._configure_internal(
                    service_name,
                    service_namespace,
                    logger_name,
                    token_resolver,
                    cluster_category,
                    **kwargs,
                )
        except Exception as e:
            self._logger.error(f"❌ Failed to configure telemetry: {e}")
            return False

    def _configure_internal(
        self,
        service_name: str,
        service_namespace: str,
        logger_name: str,
        token_resolver: Callable[[str, str], str | None] | None = None,
        cluster_category: str = "prod",
        **kwargs: Any,
    ) -> bool:
        """Internal configuration method - not thread-safe, must be called with lock."""

        # Create resource with service information
        resource = Resource.create(
            {
                SERVICE_NAMESPACE: service_namespace,
                SERVICE_NAME: service_name,
            }
        )

        # Get existing tracer provider or create new one
        try:
            tracer_provider = trace.get_tracer_provider()
            # Check if it's already configured
            if hasattr(tracer_provider, "resource") and tracer_provider.resource:
                # Already configured, just add our span processor
                agent_processor = SpanProcessor()
                tracer_provider.add_span_processor(agent_processor)
                self._tracer_provider = tracer_provider
                self._span_processors["agent"] = agent_processor
                return True
        except Exception:
            pass

        # Configure tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        self._tracer_provider = tracer_provider

        if is_agent365_exporter_enabled() and token_resolver is not None:
            exporter = Agent365Exporter(
                token_resolver=token_resolver,
                cluster_category=cluster_category,
                **kwargs,
            )
        else:
            exporter = ConsoleSpanExporter()
            self._logger.warning(
                "is_agent365_exporter_enabled() not enabled or token_resolver not set.Falling back to console exporter."
            )

        # Add span processors

        # Create BatchSpanProcessor with optimized settings
        batch_processor = BatchSpanProcessor(exporter)
        agent_processor = SpanProcessor()

        tracer_provider.add_span_processor(batch_processor)
        tracer_provider.add_span_processor(agent_processor)

        # Store references for cleanup
        self._span_processors["batch"] = batch_processor
        self._span_processors["agent"] = agent_processor

        # Configure logging if logger_name is provided
        if logger_name:
            target_logger = logging.getLogger(logger_name)
            target_logger.setLevel(logging.INFO)

        return True

    def is_configured(self) -> bool:
        """Check if the telemetry manager is configured."""
        return self._tracer_provider is not None

    def get_tracer(self, name: str | None = None, version: str | None = None):
        """
        Return an OpenTelemetry Tracer tied to the TracerProvider configured by agent365.

        If the telemetry manager is not configured yet, this returns the default
        (no-op) tracer from OpenTelemetry and logs a warning. Callers should prefer
        to call `configure(...)` during application startup so the tracer
        returned is backed by the configured TracerProvider.

        :param name: Optional tracer name. Defaults to 'microsoft_agents_a365.observability.core' when not provided.
        :param version: Optional tracer version.
        :return: An OpenTelemetry Tracer instance.
        """
        tracer_name = name or DEFAULT_LOGGER_NAME
        if self._tracer_provider is None:
            # Not configured — return whatever tracer OpenTelemetry provides (no-op)
            self._logger.warning(
                "agent365 telemetry not configured; returning a no-op tracer for '%s'", tracer_name
            )
            return trace.get_tracer(tracer_name, version)

        # Ensure global tracer provider is set (should already be by configure)
        try:
            return trace.get_tracer(tracer_name, version)
        except Exception as e:
            self._logger.error("Failed to get tracer '%s': %s", tracer_name, e)
            return trace.get_tracer(tracer_name, version)

    def get_tracer_provider(self):
        """
        Return the configured TracerProvider instance.
        """
        return self._tracer_provider


# Singleton instance
_telemetry_manager = TelemetryManager()


# Public API functions that delegate to the singleton manager
def configure(
    service_name: str,
    service_namespace: str,
    logger_name: str = DEFAULT_LOGGER_NAME,
    token_resolver: Callable[[str, str], str | None] | None = None,
    cluster_category: str = "prod",
    **kwargs: Any,
) -> bool:
    """
    Configure telemetry with OpenTelemetry.

    :param service_name: The name of the service.
    :param service_namespace: The namespace of the service.
    :param logger_name: The name of the logger to collect telemetry from.
    :return: True if configuration succeeded, False otherwise.
    """
    return _telemetry_manager.configure(
        service_name,
        service_namespace,
        logger_name,
        token_resolver,
        cluster_category,
        **kwargs,
    )


def is_configured() -> bool:
    """
    Check if telemetry is currently configured.

    :return: True if telemetry is configured and ready to use, False otherwise
    """
    return _telemetry_manager.is_configured()


def get_tracer(name: str | None = None, version: str | None = None):
    """
    Return a tracer tied to the TracerProvider configured by the SDK.

    :param name: Optional tracer name. If omitted, defaults to 'microsoft_agents_a365.observability.core'.
    :param version: Optional tracer version.
    :return: An OpenTelemetry Tracer (may be a no-op tracer if SDK isn't configured).
    """
    return _telemetry_manager.get_tracer(name, version)


def get_tracer_provider():
    """
    Return the TracerProvider configured by the SDK.

    :return: Configured OpenTelemetry TracerProvider
    """
    return _telemetry_manager.get_tracer_provider()

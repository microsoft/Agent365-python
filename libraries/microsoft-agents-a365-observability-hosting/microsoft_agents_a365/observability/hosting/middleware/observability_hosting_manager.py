# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Singleton manager for configuring hosting-layer observability middleware."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from microsoft_agents.hosting.core.middleware_set import MiddlewareSet

from .baggage_middleware import BaggageMiddleware
from .output_logging_middleware import OutputLoggingMiddleware

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityHostingOptions:
    """Configuration options for the hosting observability layer."""

    enable_baggage: bool = False
    """Enable baggage propagation middleware. Defaults to ``False``."""

    enable_output_logging: bool = False
    """Enable output logging middleware for tracing outgoing messages. Defaults to ``False``."""


class ObservabilityHostingManager:
    """Singleton manager for configuring hosting-layer observability middleware.

    Example:
        .. code-block:: python

            ObservabilityHostingManager.configure(adapter.middleware_set, ObservabilityHostingOptions(
                enable_output_logging=True,
            ))
    """

    _instance: ObservabilityHostingManager | None = None

    def __init__(self) -> None:
        """Private constructor — use :meth:`configure` instead."""

    @classmethod
    def configure(
        cls,
        middleware_set: MiddlewareSet,
        options: ObservabilityHostingOptions,
    ) -> ObservabilityHostingManager:
        """Configure the singleton instance and register middleware.

        Subsequent calls after the first are no-ops and return the existing instance.

        Args:
            middleware_set: The middleware set to register middleware on
                (e.g., ``adapter.middleware_set``).
            options: Configuration options controlling which middleware to enable.

        Returns:
            The singleton :class:`ObservabilityHostingManager` instance.

        Raises:
            TypeError: If *middleware_set* or *options* is ``None``.
        """
        if middleware_set is None:
            raise TypeError("middleware_set must not be None")
        if options is None:
            raise TypeError("options must not be None")

        if cls._instance is not None:
            logger.warning(
                "[ObservabilityHostingManager] Already configured. "
                "Subsequent configure() calls are ignored."
            )
            return cls._instance

        instance = cls()

        if options.enable_baggage:
            middleware_set.use(BaggageMiddleware())
            logger.info("[ObservabilityHostingManager] BaggageMiddleware registered.")

        if options.enable_output_logging:
            middleware_set.use(OutputLoggingMiddleware())
            logger.info("[ObservabilityHostingManager] OutputLoggingMiddleware registered.")

        logger.info(
            "[ObservabilityHostingManager] Configured. Baggage: %s, OutputLogging: %s.",
            options.enable_baggage,
            options.enable_output_logging,
        )

        cls._instance = instance
        return instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        cls._instance = None

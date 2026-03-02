# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Singleton manager for configuring hosting-layer observability middleware."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from microsoft_agents.hosting.core import ChannelAdapter

from .baggage_middleware import BaggageMiddleware
from .output_logging_middleware import OutputLoggingMiddleware

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityHostingOptions:
    """Configuration options for the hosting observability layer."""

    enable_baggage: bool = True
    """Enable baggage propagation middleware. Defaults to ``True``."""

    enable_output_logging: bool = False
    """Enable output logging middleware for tracing outgoing messages. Defaults to ``False``."""


class ObservabilityHostingManager:
    """Singleton manager for configuring hosting-layer observability middleware.

    Example:
        .. code-block:: python

            ObservabilityHostingManager.configure(adapter, ObservabilityHostingOptions(
                enable_output_logging=True,
            ))
    """

    _instance: ObservabilityHostingManager | None = None

    def __init__(self) -> None:
        """Private constructor — use :meth:`configure` instead."""

    @classmethod
    def configure(
        cls,
        adapter: ChannelAdapter,
        options: ObservabilityHostingOptions,
    ) -> ObservabilityHostingManager:
        """Configure the singleton instance and register middleware on the adapter.

        Subsequent calls after the first are no-ops and return the existing instance.

        Args:
            adapter: The channel adapter to register middleware on.
            options: Configuration options controlling which middleware to enable.

        Returns:
            The singleton :class:`ObservabilityHostingManager` instance.

        Raises:
            TypeError: If *adapter* or *options* is ``None``.
        """
        if adapter is None:
            raise TypeError("adapter must not be None")
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
            adapter.use(BaggageMiddleware())
            logger.info("[ObservabilityHostingManager] BaggageMiddleware registered.")

        if options.enable_output_logging:
            adapter.use(OutputLoggingMiddleware())
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

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import MagicMock

import pytest
from microsoft_agents_a365.observability.hosting.middleware.baggage_middleware import (
    BaggageMiddleware,
)
from microsoft_agents_a365.observability.hosting.middleware.observability_hosting_manager import (
    ObservabilityHostingManager,
    ObservabilityHostingOptions,
)
from microsoft_agents_a365.observability.hosting.middleware.output_logging_middleware import (
    OutputLoggingMiddleware,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton before and after each test."""
    ObservabilityHostingManager.reset()
    yield
    ObservabilityHostingManager.reset()


def test_configure_returns_instance():
    """configure() should return an ObservabilityHostingManager instance."""
    adapter = MagicMock()
    instance = ObservabilityHostingManager.configure(adapter)
    assert isinstance(instance, ObservabilityHostingManager)


def test_configure_is_singleton():
    """Subsequent configure() calls should return the same instance."""
    adapter = MagicMock()
    first = ObservabilityHostingManager.configure(adapter)
    second = ObservabilityHostingManager.configure(adapter)
    assert first is second


def test_configure_registers_baggage_middleware_by_default():
    """By default, BaggageMiddleware should be registered."""
    adapter = MagicMock()
    ObservabilityHostingManager.configure(adapter)

    # The adapter.use should have been called once (only BaggageMiddleware by default)
    assert adapter.use.call_count == 1
    registered = adapter.use.call_args_list[0][0][0]
    assert isinstance(registered, BaggageMiddleware)


def test_configure_registers_both_middlewares():
    """When output logging is enabled, both middlewares should be registered."""
    adapter = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=True, enable_output_logging=True)
    ObservabilityHostingManager.configure(adapter, options)

    assert adapter.use.call_count == 2
    registered_types = [c[0][0] for c in adapter.use.call_args_list]
    assert isinstance(registered_types[0], BaggageMiddleware)
    assert isinstance(registered_types[1], OutputLoggingMiddleware)


def test_configure_disables_baggage():
    """When baggage is disabled, only output logging should be registered (if enabled)."""
    adapter = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=False, enable_output_logging=True)
    ObservabilityHostingManager.configure(adapter, options)

    assert adapter.use.call_count == 1
    registered = adapter.use.call_args_list[0][0][0]
    assert isinstance(registered, OutputLoggingMiddleware)


def test_configure_disables_all():
    """When both are disabled, no middleware should be registered."""
    adapter = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=False, enable_output_logging=False)
    ObservabilityHostingManager.configure(adapter, options)

    adapter.use.assert_not_called()


def test_configure_no_adapter():
    """When no adapter is provided, no middleware should be registered."""
    instance = ObservabilityHostingManager.configure()
    assert isinstance(instance, ObservabilityHostingManager)


def test_configure_no_adapter_subsequent_call_ignored():
    """Subsequent calls after no-adapter configure should still be no-ops."""
    first = ObservabilityHostingManager.configure()
    adapter = MagicMock()
    second = ObservabilityHostingManager.configure(adapter)
    assert first is second
    adapter.use.assert_not_called()

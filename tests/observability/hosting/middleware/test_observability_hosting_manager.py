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
    instance = ObservabilityHostingManager.configure(adapter, ObservabilityHostingOptions())
    assert isinstance(instance, ObservabilityHostingManager)


def test_configure_is_singleton():
    """Subsequent configure() calls should return the same instance."""
    adapter = MagicMock()
    options = ObservabilityHostingOptions()
    first = ObservabilityHostingManager.configure(adapter, options)
    second = ObservabilityHostingManager.configure(adapter, options)
    assert first is second


def test_configure_registers_baggage_middleware_by_default():
    """By default, BaggageMiddleware should be registered."""
    adapter = MagicMock()
    ObservabilityHostingManager.configure(adapter, ObservabilityHostingOptions())

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


def test_configure_raises_on_none_adapter():
    """configure() should raise TypeError when adapter is None."""
    with pytest.raises(TypeError, match="adapter must not be None"):
        ObservabilityHostingManager.configure(None, ObservabilityHostingOptions())


def test_configure_raises_on_none_options():
    """configure() should raise TypeError when options is None."""
    adapter = MagicMock()
    with pytest.raises(TypeError, match="options must not be None"):
        ObservabilityHostingManager.configure(adapter, None)

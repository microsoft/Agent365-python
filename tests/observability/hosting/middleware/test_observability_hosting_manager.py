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
    middleware_set = MagicMock()
    instance = ObservabilityHostingManager.configure(middleware_set, ObservabilityHostingOptions())
    assert isinstance(instance, ObservabilityHostingManager)


def test_configure_is_singleton():
    """Subsequent configure() calls should return the same instance."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions()
    first = ObservabilityHostingManager.configure(middleware_set, options)
    second = ObservabilityHostingManager.configure(middleware_set, options)
    assert first is second


def test_configure_registers_baggage_middleware_by_default():
    """By default, BaggageMiddleware should be registered."""
    middleware_set = MagicMock()
    ObservabilityHostingManager.configure(middleware_set, ObservabilityHostingOptions())

    # The middleware_set.use should have been called once (only BaggageMiddleware by default)
    assert middleware_set.use.call_count == 1
    registered = middleware_set.use.call_args_list[0][0][0]
    assert isinstance(registered, BaggageMiddleware)


def test_configure_registers_both_middlewares():
    """When output logging is enabled, both middlewares should be registered."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=True, enable_output_logging=True)
    ObservabilityHostingManager.configure(middleware_set, options)

    assert middleware_set.use.call_count == 2
    registered_types = [c[0][0] for c in middleware_set.use.call_args_list]
    assert isinstance(registered_types[0], BaggageMiddleware)
    assert isinstance(registered_types[1], OutputLoggingMiddleware)


def test_configure_disables_baggage():
    """When baggage is disabled, only output logging should be registered (if enabled)."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=False, enable_output_logging=True)
    ObservabilityHostingManager.configure(middleware_set, options)

    assert middleware_set.use.call_count == 1
    registered = middleware_set.use.call_args_list[0][0][0]
    assert isinstance(registered, OutputLoggingMiddleware)


def test_configure_disables_all():
    """When both are disabled, no middleware should be registered."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions(enable_baggage=False, enable_output_logging=False)
    ObservabilityHostingManager.configure(middleware_set, options)

    middleware_set.use.assert_not_called()


def test_configure_raises_on_none_middleware_set():
    """configure() should raise TypeError when middleware_set is None."""
    with pytest.raises(TypeError, match="middleware_set must not be None"):
        ObservabilityHostingManager.configure(None, ObservabilityHostingOptions())


def test_configure_raises_on_none_options():
    """configure() should raise TypeError when options is None."""
    middleware_set = MagicMock()
    with pytest.raises(TypeError, match="options must not be None"):
        ObservabilityHostingManager.configure(middleware_set, None)

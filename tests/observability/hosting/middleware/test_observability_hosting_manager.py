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
    ObservabilityHostingManager._reset()
    yield
    ObservabilityHostingManager._reset()


def test_configure_is_singleton():
    """configure() should return an ObservabilityHostingManager and be a singleton."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions()
    first = ObservabilityHostingManager.configure(middleware_set, options)
    assert isinstance(first, ObservabilityHostingManager)
    second = ObservabilityHostingManager.configure(middleware_set, options)
    assert first is second


@pytest.mark.parametrize(
    "enable_baggage,enable_output_logging,expected_types",
    [
        (True, False, [BaggageMiddleware]),
        (True, True, [BaggageMiddleware, OutputLoggingMiddleware]),
        (False, True, [OutputLoggingMiddleware]),
        (False, False, []),
    ],
    ids=["default_baggage_only", "both_enabled", "output_only", "none"],
)
def test_configure_registers_expected_middlewares(
    enable_baggage, enable_output_logging, expected_types
):
    """configure() should register the correct middlewares based on options."""
    middleware_set = MagicMock()
    options = ObservabilityHostingOptions(
        enable_baggage=enable_baggage, enable_output_logging=enable_output_logging
    )
    ObservabilityHostingManager.configure(middleware_set, options)

    assert middleware_set.use.call_count == len(expected_types)
    for call, expected_type in zip(middleware_set.use.call_args_list, expected_types, strict=True):
        assert isinstance(call[0][0], expected_type)


@pytest.mark.parametrize(
    "middleware_set,options,match",
    [
        (None, ObservabilityHostingOptions(), "middleware_set must not be None"),
        (MagicMock(), None, "options must not be None"),
    ],
    ids=["none_middleware_set", "none_options"],
)
def test_configure_raises_on_none(middleware_set, options, match):
    """configure() should raise TypeError when required args are None."""
    with pytest.raises(TypeError, match=match):
        ObservabilityHostingManager.configure(middleware_set, options)

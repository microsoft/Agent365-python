# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for environment_utils module."""

import pytest

from microsoft_agents_a365.runtime.environment_utils import (
    PROD_OBSERVABILITY_SCOPE,
    get_observability_authentication_scope,
    is_development_environment,
)


def test_get_observability_authentication_scope():
    """Test get_observability_authentication_scope returns production scope."""
    result = get_observability_authentication_scope()
    assert result == [PROD_OBSERVABILITY_SCOPE]


def test_get_observability_authentication_scope_with_override(monkeypatch):
    """Test get_observability_authentication_scope returns override when env var is set."""
    override_scope = "https://override.example.com/.default"
    monkeypatch.setenv("A365_OBSERVABILITY_SCOPE_OVERRIDE", override_scope)

    result = get_observability_authentication_scope()
    assert result == [override_scope]


@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, False),
        ("Development", True),
        ("production", False),
        ("staging", False),
    ],
)
def test_is_development_environment(monkeypatch, env_value, expected):
    """Test is_development_environment returns correct value based on PYTHON_ENVIRONMENT."""
    if env_value is None:
        monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("PYTHON_ENVIRONMENT", env_value)

    result = is_development_environment()
    assert result == expected

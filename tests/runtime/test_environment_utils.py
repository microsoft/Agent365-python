# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for environment_utils module."""

import pytest
from microsoft_agents_a365.runtime.environment_utils import (
    is_development_environment,
)


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

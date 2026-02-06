# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for version_utils module."""

import warnings

import pytest
from microsoft_agents_a365.runtime.version_utils import build_version


# Tests for build_version
@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, "0.0.0"),
        ("1.2.3", "1.2.3"),
        ("2.5.0-beta", "2.5.0-beta"),
        ("", ""),
    ],
)
def test_build_version(monkeypatch, env_value, expected):
    """Test build_version returns correct version based on environment variable."""
    if env_value is None:
        monkeypatch.delenv("AGENT365_PYTHON_SDK_PACKAGE_VERSION", raising=False)
    else:
        monkeypatch.setenv("AGENT365_PYTHON_SDK_PACKAGE_VERSION", env_value)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = build_version()

    assert result == expected


def test_build_version_deprecation_warning():
    """Test that build_version raises DeprecationWarning with correct message."""
    with pytest.warns(
        DeprecationWarning, match="build_version.*deprecated.*setuptools-git-versioning"
    ):
        build_version()

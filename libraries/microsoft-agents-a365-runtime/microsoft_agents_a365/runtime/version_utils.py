# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Version utilities for Microsoft Agent 365 SDK packages.

This module is deprecated. Versioning is now handled automatically by
setuptools-git-versioning. See versioning/TARGET-VERSION and
HOW_TO_SET_A_VERSION.md for details.
"""

from __future__ import annotations

import os


def build_version():
    """
    DEPRECATED: This function is no longer used.

    Version is now automatically calculated by setuptools-git-versioning
    based on Git history and tags. See HOW_TO_SET_A_VERSION.md for details.

    Returns:
        str: Version from AGENT365_PYTHON_SDK_PACKAGE_VERSION environment variable or "0.0.0"
    """
    import warnings

    warnings.warn(
        "build_version() is deprecated. Version is now managed by setuptools-git-versioning.",
        DeprecationWarning,
        stacklevel=2,
    )
    return os.environ.get("AGENT365_PYTHON_SDK_PACKAGE_VERSION", "0.0.0")

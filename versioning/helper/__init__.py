# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Microsoft Agent 365 Python SDK setup utilities."""

from .setup_utils import (
    get_package_version,
    get_dynamic_dependencies,
    get_base_version,
    get_next_major_version,
)

__all__ = [
    "get_package_version",
    "get_dynamic_dependencies",
    "get_base_version",
    "get_next_major_version",
]

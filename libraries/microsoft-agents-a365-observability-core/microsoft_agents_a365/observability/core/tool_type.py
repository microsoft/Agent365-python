# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Tool type enum.

from enum import Enum


class ToolType(Enum):
    """Enumeration for different tool types for execute tool contexts."""

    FUNCTION = "function"
    EXTENSION = "extension"
    DATASTORE = "datastore"

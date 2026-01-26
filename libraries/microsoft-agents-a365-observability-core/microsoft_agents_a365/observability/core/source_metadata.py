# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Source metadata class.

from dataclasses import dataclass


@dataclass
class SourceMetadata:
    """Source metadata for agent execution context."""

    id: str | None = None
    name: str | None = None
    icon_uri: str | None = None
    description: str | None = None

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Channel class.

from dataclasses import dataclass


@dataclass
class Channel:
    """Channel information for agent execution context."""

    name: str | None = None
    link: str | None = None

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass


@dataclass
class Response:
    """Response details from agent execution."""

    messages: list[str]
    """The list of response messages."""

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass


@dataclass
class Response:
    """Response details from agent execution."""

    """The list of response messages from the agent."""
    messages: list[str]

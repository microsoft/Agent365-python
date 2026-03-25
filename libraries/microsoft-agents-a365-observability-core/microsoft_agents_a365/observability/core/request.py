# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Request class.

from dataclasses import dataclass

from .channel import Channel


@dataclass
class Request:
    """Request details for agent execution."""

    content: str | None = None
    session_id: str | None = None
    channel: Channel | None = None
    conversation_id: str | None = None

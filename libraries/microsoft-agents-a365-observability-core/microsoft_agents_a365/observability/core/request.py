# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Request class.

from __future__ import annotations

from dataclasses import dataclass

from .channel import Channel
from .models.messages import InputMessagesParam


@dataclass
class Request:
    """Request details for agent execution."""

    content: InputMessagesParam | None = None
    session_id: str | None = None
    channel: Channel | None = None
    conversation_id: str | None = None

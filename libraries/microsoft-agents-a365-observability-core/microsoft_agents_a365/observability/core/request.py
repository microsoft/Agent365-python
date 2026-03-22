# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Request class.

from dataclasses import dataclass

from .execution_type import ExecutionType
from .channel import Channel


@dataclass
class Request:
    """Request details for agent execution."""

    content: str
    execution_type: ExecutionType
    session_id: str | None = None
    channel: Channel | None = None

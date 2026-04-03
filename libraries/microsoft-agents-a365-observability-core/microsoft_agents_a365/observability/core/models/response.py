# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .messages import OutputMessagesParam, ToolOutputMessages

ResponseMessagesParam = Union[OutputMessagesParam, ToolOutputMessages]
"""Accepted type for Response.messages.

Supports plain strings, OutputMessages, or ToolOutputMessages.
"""


@dataclass
class Response:
    """Response details from agent execution.

    Accepts plain strings (backward compat), structured OTEL OutputMessages,
    or ToolOutputMessages.
    """

    messages: ResponseMessagesParam

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .messages import OutputMessagesParam, ToolOutputParam

ResponseMessagesParam = Union[OutputMessagesParam, ToolOutputParam]
"""Accepted type for Response.messages.

Supports plain strings, OutputMessages, or ToolOutputMessages (and their string equivalents).
"""


@dataclass
class Response:
    """Response details from agent execution.

    Accepts plain strings (backward compat), structured OTEL OutputMessages,
    or ToolOutputMessages.
    """

    messages: ResponseMessagesParam

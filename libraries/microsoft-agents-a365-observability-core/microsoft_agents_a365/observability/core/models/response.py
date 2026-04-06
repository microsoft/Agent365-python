# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .messages import OutputMessagesParam, ToolOutputParam

ResponseMessagesParam = Union[OutputMessagesParam, ToolOutputParam]
"""Accepted type for Response.messages.

Plain strings (``str`` or ``list[str]``) are treated as assistant output messages
and normalized via ``OutputMessages``. To record tool output, pass an explicit
``ToolOutputMessages`` wrapper — plain strings cannot be distinguished as tool
output at runtime.
"""


@dataclass
class Response:
    """Response details from agent execution.

    Accepts plain strings (backward compat) or structured ``OutputMessages``.
    For tool output, pass an explicit ``ToolOutputMessages`` wrapper.
    """

    messages: ResponseMessagesParam

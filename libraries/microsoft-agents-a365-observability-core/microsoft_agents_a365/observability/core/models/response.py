# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .messages import OutputMessagesParam

ResponseMessagesParam = Union[OutputMessagesParam, dict[str, object]]
"""Accepted type for Response.messages.

Supports plain strings, ``OutputMessages``, or a structured tool result dict.
A ``dict[str, object]`` is treated as a tool call result per OTEL spec and
serialized directly via ``json.dumps``.
"""


@dataclass
class Response:
    """Response details from agent execution.

    Accepts plain strings (backward compat), structured ``OutputMessages``,
    or a ``dict`` for tool call results (per OTEL spec).
    """

    messages: ResponseMessagesParam

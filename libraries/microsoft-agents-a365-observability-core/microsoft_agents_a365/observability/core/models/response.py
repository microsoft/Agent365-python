# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass

from .messages import OutputMessagesParam


@dataclass
class Response:
    """Response details from agent execution.

    Accepts plain strings (backward compat) or structured OTEL OutputMessages.
    """

    messages: OutputMessagesParam

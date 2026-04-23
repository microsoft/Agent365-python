# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Conversion and serialization helpers for OTEL gen-ai message format.

Provides normalization from plain ``list[str]`` (backward compat) to the
versioned wrapper format, and a non-throwing ``serialize_messages`` function.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from enum import Enum
from typing import Union

from .models.messages import (
    A365_MESSAGE_SCHEMA_VERSION,
    ChatMessage,
    InputMessages,
    InputMessagesParam,
    MessageRole,
    OutputMessage,
    OutputMessages,
    OutputMessagesParam,
    TextPart,
)

logger = logging.getLogger(__name__)


def is_string_list(
    param: Union[InputMessagesParam, OutputMessagesParam],
) -> bool:
    """Return ``True`` when *param* is a plain ``list[str]``."""
    return isinstance(param, list) and all(isinstance(item, str) for item in param)


def is_wrapped_messages(
    param: Union[InputMessagesParam, OutputMessagesParam],
) -> bool:
    """Return ``True`` when *param* is a versioned wrapper."""
    return isinstance(param, (InputMessages, OutputMessages))


# ---------------------------------------------------------------------------
# Plain-string → structured conversion
# ---------------------------------------------------------------------------


def to_input_messages(messages: list[str]) -> list[ChatMessage]:
    """Convert plain input strings into OTEL ``ChatMessage`` objects."""
    return [
        ChatMessage(role=MessageRole.USER, parts=[TextPart(content=content)])
        for content in messages
    ]


def to_output_messages(messages: list[str]) -> list[OutputMessage]:
    """Convert plain output strings into OTEL ``OutputMessage`` objects."""
    return [
        OutputMessage(role=MessageRole.ASSISTANT, parts=[TextPart(content=content)])
        for content in messages
    ]


# ---------------------------------------------------------------------------
# Normalization (union → versioned wrapper)
# ---------------------------------------------------------------------------


def normalize_input_messages(param: InputMessagesParam) -> InputMessages:
    """Normalize an ``InputMessagesParam`` to a versioned ``InputMessages`` wrapper.

    - ``str`` → wrapped in a single-element list, then converted.
    - ``list[str]`` → converted to ``ChatMessage`` list and wrapped.
    - ``InputMessages`` → returned as-is.
    """
    if isinstance(param, str):
        return InputMessages(messages=to_input_messages([param]))
    if is_string_list(param):
        return InputMessages(messages=to_input_messages(param))  # type: ignore[arg-type]
    return param  # type: ignore[return-value]


def normalize_output_messages(param: OutputMessagesParam) -> OutputMessages:
    """Normalize an ``OutputMessagesParam`` to a versioned ``OutputMessages`` wrapper.

    - ``str`` → wrapped in a single-element list, then converted.
    - ``list[str]`` → converted to ``OutputMessage`` list and wrapped.
    - ``OutputMessages`` → returned as-is.
    """
    if isinstance(param, str):
        return OutputMessages(messages=to_output_messages([param]))
    if is_string_list(param):
        return OutputMessages(messages=to_output_messages(param))  # type: ignore[arg-type]
    return param  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _message_dict_factory(items: list[tuple[str, object]]) -> dict[str, object]:
    """Custom dict factory for ``dataclasses.asdict``.

    Drops ``None`` values and converts enum members to their string value.
    """
    return {k: (v.value if isinstance(v, Enum) else v) for k, v in items if v is not None}


def serialize_messages(
    wrapper: Union[InputMessages, OutputMessages],
) -> str:
    """Serialize a versioned message wrapper to JSON.

    The output is the full wrapper object:
    ``{"version":"0.1.0","messages":[...]}``.

    The try/except ensures telemetry recording is non-throwing even when
    message parts contain non-JSON-serializable values.
    """
    try:
        return json.dumps(
            asdict(wrapper, dict_factory=_message_dict_factory),
            default=str,
            ensure_ascii=False,
        )
    except Exception:
        logger.warning("Failed to serialize messages; using fallback.", exc_info=True)
        messages = getattr(wrapper, "messages", [])
        count = len(messages) if isinstance(messages, list) else 0
        noun = "message" if count == 1 else "messages"
        fallback = {
            "version": A365_MESSAGE_SCHEMA_VERSION,
            "messages": [
                {
                    "role": MessageRole.SYSTEM.value,
                    "parts": [
                        {
                            "type": "text",
                            "content": f"[serialization failed: {count} {noun}]",
                        }
                    ],
                }
            ],
        }
        return json.dumps(fallback, ensure_ascii=False)

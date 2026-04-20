# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Maps Agent Framework span tag messages to A365 versioned message format.

Agent Framework sets ``gen_ai.input.messages`` / ``gen_ai.output.messages`` as span
tags containing JSON arrays of ``{role, parts[{type, content}], finish_reason?}``.
This mapper converts them to :class:`InputMessages` / :class:`OutputMessages`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from microsoft_agents_a365.observability.core.message_utils import serialize_messages
from microsoft_agents_a365.observability.core.models.messages import (
    BlobPart,
    ChatMessage,
    FilePart,
    GenericPart,
    InputMessages,
    MessagePart,
    MessageRole,
    OutputMessage,
    OutputMessages,
    ReasoningPart,
    TextPart,
    ToolCallRequestPart,
    ToolCallResponsePart,
    UriPart,
)

logger = logging.getLogger(__name__)

_ROLE_MAP: dict[str, MessageRole] = {
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "tool": MessageRole.TOOL,
}


def map_input_messages(messages_json: str) -> str | None:
    """Map a ``gen_ai.input.messages`` tag value to a serialized A365 JSON string.

    Args:
        messages_json: The raw JSON string from the span attribute.

    Returns:
        Serialized :class:`InputMessages` JSON string, or ``None`` if the
        input is empty or cannot be parsed.
    """
    try:
        raw = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        logger.debug("Failed to parse input messages JSON: %s", messages_json[:200])
        return None

    if not isinstance(raw, list):
        return None

    chat_messages: list[ChatMessage] = []
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        role = _map_role(msg.get("role"), MessageRole.USER)
        parts = _map_parts(msg)
        if parts:
            chat_messages.append(ChatMessage(role=role, parts=parts, name=msg.get("name")))

    if not chat_messages:
        return None

    return serialize_messages(InputMessages(messages=chat_messages))


def map_output_messages(messages_json: str) -> str | None:
    """Map a ``gen_ai.output.messages`` tag value to a serialized A365 JSON string.

    Args:
        messages_json: The raw JSON string from the span attribute.

    Returns:
        Serialized :class:`OutputMessages` JSON string, or ``None`` if the
        input is empty or cannot be parsed.
    """
    try:
        raw = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        logger.debug("Failed to parse output messages JSON: %s", messages_json[:200])
        return None

    if not isinstance(raw, list):
        return None

    output_messages: list[OutputMessage] = []
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        role = _map_role(msg.get("role"), MessageRole.ASSISTANT)
        parts = _map_parts(msg)
        finish_reason = msg.get("finish_reason")
        if parts:
            output_messages.append(
                OutputMessage(role=role, parts=parts, finish_reason=finish_reason)
            )

    if not output_messages:
        return None

    return serialize_messages(OutputMessages(messages=output_messages))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _map_role(role: str | None, default: MessageRole) -> MessageRole:
    """Map a raw role string to a :class:`MessageRole` enum."""
    if not role:
        return default
    return _ROLE_MAP.get(role.lower(), default)


def _map_parts(msg: dict[str, Any]) -> list[MessagePart]:
    """Map all parts in a raw message dict."""
    parts_data = msg.get("parts", [])
    if not isinstance(parts_data, list):
        return []
    mapped = [_map_single_part(p) for p in parts_data if isinstance(p, dict)]
    return [p for p in mapped if p is not None]


def _map_single_part(part: dict[str, Any]) -> MessagePart | None:
    """Map a single raw part dict to the appropriate A365 message part."""
    part_type = part.get("type", "")

    if part_type == "text":
        content = part.get("content", "")
        return TextPart(content=content) if content else None

    if part_type == "reasoning":
        content = part.get("content", "")
        return ReasoningPart(content=content) if content else None

    if part_type == "tool_call":
        name = part.get("name")
        if not name:
            return None
        return ToolCallRequestPart(
            name=name,
            id=part.get("id"),
            arguments=part.get("arguments"),
        )

    if part_type == "tool_call_response":
        return ToolCallResponsePart(
            id=part.get("id"),
            response=part.get("response"),
        )

    if part_type == "blob":
        modality = part.get("modality", "")
        content = part.get("content", "")
        if not modality or not content:
            return None
        return BlobPart(modality=modality, content=content, mime_type=part.get("mime_type"))

    if part_type == "file":
        modality = part.get("modality", "")
        file_id = part.get("file_id", "")
        if not modality or not file_id:
            return None
        return FilePart(modality=modality, file_id=file_id, mime_type=part.get("mime_type"))

    if part_type == "uri":
        modality = part.get("modality", "")
        uri = part.get("uri", "")
        if not modality or not uri:
            return None
        return UriPart(modality=modality, uri=uri, mime_type=part.get("mime_type"))

    # Fallback: GenericPart for unknown/future part types
    data = {k: v for k, v in part.items() if k != "type"}
    return GenericPart(type=part_type, data=data) if part_type else None

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Maps OpenAI span tag messages to A365 versioned message format.

Handles three input shapes produced by the OpenAI trace processor:

1. **Chat-completions format** (from ``GenerationSpanData``):
   ``[{"role":"system","content":"..."}, ...]``
2. **Response API format** (from ``ResponseSpanData``):
   - Input: ``[{"type":"message","role":"user","content":"..."}, ...]``
   - Output: ``{"id":"...","model":"...","output":[...], ...}`` (full Response JSON)
3. **Plain string** (from ``AgentSpanData``):
   A bare user/assistant message captured from child generation spans.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from microsoft_agents_a365.observability.core.message_utils import serialize_messages
from microsoft_agents_a365.observability.core.models.messages import (
    ChatMessage,
    InputMessages,
    MessagePart,
    MessageRole,
    OutputMessage,
    OutputMessages,
    TextPart,
    ToolCallRequestPart,
    ToolCallResponsePart,
)

logger = logging.getLogger(__name__)

_ROLE_MAP: dict[str, MessageRole] = {
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "tool": MessageRole.TOOL,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_input_messages(messages_json: str) -> str | None:
    """Map a ``gen_ai.input.messages`` tag value to a serialized A365 JSON string.

    Args:
        messages_json: The raw JSON string from the span attribute.

    Returns:
        Serialized ``InputMessages`` JSON string, or ``None`` if the
        input is empty or cannot be parsed.
    """
    if not messages_json:
        return None

    # Plain string (AgentSpanData captures bare user text)
    try:
        raw = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        return _wrap_plain_input(messages_json)

    if isinstance(raw, list):
        return _map_input_list(raw)

    # Unexpected shape
    return _wrap_plain_input(messages_json)


def map_output_messages(messages_json: str) -> str | None:
    """Map a ``gen_ai.output.messages`` tag value to a serialized A365 JSON string.

    Args:
        messages_json: The raw JSON string from the span attribute.

    Returns:
        Serialized ``OutputMessages`` JSON string, or ``None`` if the
        input is empty or cannot be parsed.
    """
    if not messages_json:
        return None

    try:
        raw = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        return _wrap_plain_output(messages_json)

    if isinstance(raw, list):
        return _map_output_list(raw)

    if isinstance(raw, dict):
        # Full Response JSON from ResponseSpanData (model_dump_json)
        return _map_response_output(raw)

    return _wrap_plain_output(messages_json)


# ---------------------------------------------------------------------------
# Input mapping
# ---------------------------------------------------------------------------


def _map_input_list(items: list[Any]) -> str | None:
    """Map a list of input items (chat completions or ResponseInputItemParam)."""
    chat_messages: list[ChatMessage] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")

        if item_type == "function_call":
            # ResponseInputItemParam: function_call → assistant tool call request
            name = item.get("name", "")
            if name:
                parts: list[MessagePart] = [
                    ToolCallRequestPart(
                        name=name,
                        id=item.get("call_id"),
                        arguments=item.get("arguments"),
                    )
                ]
                chat_messages.append(ChatMessage(role=MessageRole.ASSISTANT, parts=parts))

        elif item_type == "function_call_output":
            # ResponseInputItemParam: function_call_output → tool response
            parts = [
                ToolCallResponsePart(
                    id=item.get("call_id"),
                    response=item.get("output"),
                )
            ]
            chat_messages.append(ChatMessage(role=MessageRole.TOOL, parts=parts))

        elif item_type == "custom_tool_call":
            name = item.get("name", "")
            if name:
                input_data = item.get("input")
                args = json.dumps({"input": input_data}) if input_data is not None else None
                parts = [ToolCallRequestPart(name=name, id=item.get("call_id"), arguments=args)]
                chat_messages.append(ChatMessage(role=MessageRole.ASSISTANT, parts=parts))

        elif item_type == "custom_tool_call_output":
            parts = [
                ToolCallResponsePart(
                    id=item.get("call_id"),
                    response=item.get("output"),
                )
            ]
            chat_messages.append(ChatMessage(role=MessageRole.TOOL, parts=parts))

        elif item_type == "message" or "role" in item:
            # Standard message (ResponseInputItemParam or chat completions)
            mapped = _map_chat_completions_message(item)
            if mapped is not None:
                chat_messages.append(mapped)

        else:
            # Unknown type, try as generic message
            mapped = _map_chat_completions_message(item)
            if mapped is not None:
                chat_messages.append(mapped)

    if not chat_messages:
        return None
    return serialize_messages(InputMessages(messages=chat_messages))


def _map_chat_completions_message(msg: dict[str, Any]) -> ChatMessage | None:
    """Map a single chat-completions-style message dict."""
    role_str = msg.get("role", "")
    role = _ROLE_MAP.get(str(role_str).lower(), MessageRole.USER)
    parts: list[MessagePart] = []

    # Tool response message
    if role == MessageRole.TOOL:
        content = msg.get("content", "")
        tool_call_id = msg.get("tool_call_id")
        response = str(content) if content else ""
        if response or tool_call_id:
            parts.append(ToolCallResponsePart(id=tool_call_id, response=response))
        return ChatMessage(role=role, parts=parts) if parts else None

    # Text content (string or list)
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(TextPart(content=content))
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in ("input_text", "text"):
                    text = item.get("text", "")
                    if text:
                        parts.append(TextPart(content=text))
                elif item.get("type") == "output_text":
                    text = item.get("text", "")
                    if text:
                        parts.append(TextPart(content=text))

    # Tool calls
    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function", {})
            if isinstance(func, dict):
                name = func.get("name")
                if name:
                    parts.append(
                        ToolCallRequestPart(
                            name=name,
                            id=tc.get("id"),
                            arguments=func.get("arguments"),
                        )
                    )

    if not parts:
        return None
    return ChatMessage(role=role, parts=parts, name=msg.get("name"))


# ---------------------------------------------------------------------------
# Output mapping
# ---------------------------------------------------------------------------


def _map_output_list(items: list[Any]) -> str | None:
    """Map a list of chat-completions-style output messages."""
    output_messages: list[OutputMessage] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        role_str = item.get("role", "assistant")
        role = _ROLE_MAP.get(str(role_str).lower(), MessageRole.ASSISTANT)
        parts: list[MessagePart] = []

        # Tool response
        if role == MessageRole.TOOL:
            content = item.get("content", "")
            tool_call_id = item.get("tool_call_id")
            response = str(content) if content else ""
            if response or tool_call_id:
                parts.append(ToolCallResponsePart(id=tool_call_id, response=response))
        else:
            # Text content
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(TextPart(content=content))
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict):
                        text = c.get("text", "")
                        if text:
                            parts.append(TextPart(content=text))

            # Tool calls
            tool_calls = item.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    func = tc.get("function", {})
                    if isinstance(func, dict):
                        name = func.get("name")
                        if name:
                            parts.append(
                                ToolCallRequestPart(
                                    name=name,
                                    id=tc.get("id"),
                                    arguments=func.get("arguments"),
                                )
                            )

        finish_reason = item.get("finish_reason")
        if parts:
            output_messages.append(
                OutputMessage(role=role, parts=parts, finish_reason=finish_reason)
            )

    if not output_messages:
        return None
    return serialize_messages(OutputMessages(messages=output_messages))


def _map_response_output(response: dict[str, Any]) -> str | None:
    """Map a full OpenAI Response JSON to A365 OutputMessages.

    The Response object has ``output: [...]`` containing items with
    ``type`` of ``message`` or ``function_call``.
    """
    output_items = response.get("output")
    if not isinstance(output_items, list):
        return None

    output_messages: list[OutputMessage] = []

    for item in output_items:
        if not isinstance(item, Mapping):
            continue
        item_type = item.get("type")

        if item_type == "message":
            parts: list[MessagePart] = []
            role_str = item.get("role", "assistant")
            role = _ROLE_MAP.get(str(role_str).lower(), MessageRole.ASSISTANT)

            for content_item in item.get("content", []):
                if isinstance(content_item, Mapping):
                    content_type = content_item.get("type")
                    if content_type == "output_text":
                        text = content_item.get("text", "")
                        if text:
                            parts.append(TextPart(content=text))
                    elif content_type == "refusal":
                        text = content_item.get("refusal", "")
                        if text:
                            parts.append(TextPart(content=text))

            if parts:
                finish_reason = item.get("status")
                output_messages.append(
                    OutputMessage(role=role, parts=parts, finish_reason=finish_reason)
                )

        elif item_type == "function_call":
            name = item.get("name", "")
            if name:
                parts = [
                    ToolCallRequestPart(
                        name=name,
                        id=item.get("call_id"),
                        arguments=item.get("arguments"),
                    )
                ]
                output_messages.append(
                    OutputMessage(
                        role=MessageRole.ASSISTANT,
                        parts=parts,
                        finish_reason="tool_call",
                    )
                )

    if not output_messages:
        return None
    return serialize_messages(OutputMessages(messages=output_messages))


# ---------------------------------------------------------------------------
# Plain-string wrappers
# ---------------------------------------------------------------------------


def _wrap_plain_input(text: str) -> str | None:
    """Wrap a plain text string as a versioned InputMessages."""
    if not text or not text.strip():
        return None
    return serialize_messages(
        InputMessages(messages=[ChatMessage(role=MessageRole.USER, parts=[TextPart(content=text)])])
    )


def _wrap_plain_output(text: str) -> str | None:
    """Wrap a plain text string as a versioned OutputMessages."""
    if not text or not text.strip():
        return None
    return serialize_messages(
        OutputMessages(
            messages=[OutputMessage(role=MessageRole.ASSISTANT, parts=[TextPart(content=text)])]
        )
    )

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Maps LangChain messages to A365 versioned message format.

LangChain provides ``BaseMessage`` objects (``HumanMessage``, ``AIMessage``,
``SystemMessage``, ``ToolMessage``) in ``run.inputs["messages"]`` and
``run.outputs["generations"]``. This mapper converts them to the A365
versioned format (``InputMessages`` / ``OutputMessages``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from langchain_core.messages import BaseMessage

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
    "human": MessageRole.USER,
    "user": MessageRole.USER,
    "ai": MessageRole.ASSISTANT,
    "assistant": MessageRole.ASSISTANT,
    "system": MessageRole.SYSTEM,
    "tool": MessageRole.TOOL,
}


def map_input_messages(inputs: Mapping[str, Any] | None) -> str | None:
    """Map LangChain input messages to a serialized A365 InputMessages JSON string.

    Args:
        inputs: The ``run.inputs`` mapping from a LangChain run.

    Returns:
        Serialized InputMessages JSON string, or None if no messages found.
    """
    if not inputs or not isinstance(inputs, Mapping):
        return None

    multiple_messages = inputs.get("messages")
    if not multiple_messages or not isinstance(multiple_messages, Iterable):
        return None

    first_messages = next(iter(multiple_messages), None)
    if not first_messages:
        return None

    # Normalize to a list
    if isinstance(first_messages, BaseMessage):
        first_messages = [first_messages]
    elif not isinstance(first_messages, list):
        return None

    chat_messages: list[ChatMessage] = []
    for msg in first_messages:
        mapped = _map_base_message(msg)
        if mapped is not None:
            chat_messages.append(mapped)

    if not chat_messages:
        return None

    return serialize_messages(InputMessages(messages=chat_messages))


def map_output_messages(outputs: Mapping[str, Any] | None) -> str | None:
    """Map LangChain output messages to a serialized A365 OutputMessages JSON string.

    Args:
        outputs: The ``run.outputs`` mapping from a LangChain run.

    Returns:
        Serialized OutputMessages JSON string, or None if no messages found.
    """
    if not outputs or not isinstance(outputs, Mapping):
        return None

    multiple_generations = outputs.get("generations")
    if not multiple_generations or not isinstance(multiple_generations, Iterable):
        return None

    first_generations = next(iter(multiple_generations), None)
    if not first_generations or not isinstance(first_generations, Iterable):
        return None

    output_messages: list[OutputMessage] = []
    for generation in first_generations:
        if not isinstance(generation, Mapping):
            continue
        message_data = generation.get("message")
        if message_data is None:
            continue

        mapped = _map_to_output_message(message_data, generation)
        if mapped is not None:
            output_messages.append(mapped)

    if not output_messages:
        return None

    return serialize_messages(OutputMessages(messages=output_messages))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _map_role(
    msg: BaseMessage | Mapping[str, Any], default: MessageRole = MessageRole.USER
) -> MessageRole:
    """Extract the role from a LangChain message."""
    if isinstance(msg, BaseMessage):
        role_str = msg.type
    elif isinstance(msg, Mapping):
        # Direct type field (e.g. "human", "ai", "system", "tool")
        role_str = msg.get("type", "")
        # LC serialization uses "constructor" as type with role in kwargs
        if role_str == "constructor":
            kwargs = msg.get("kwargs", {})
            role_str = kwargs.get("type", "") if isinstance(kwargs, Mapping) else ""
        # Also check "role" field
        if not role_str or role_str not in _ROLE_MAP:
            role_str = msg.get("role", role_str)
    else:
        role_str = ""
    return _ROLE_MAP.get(role_str.lower(), default)


def _extract_parts(msg: BaseMessage | Mapping[str, Any]) -> list[MessagePart]:
    """Extract message parts from a LangChain message."""
    parts: list[MessagePart] = []

    # Extract content and tool_calls
    if isinstance(msg, BaseMessage):
        content = msg.content
        tool_calls = getattr(msg, "tool_calls", None)
        msg_type = msg.type
        tool_call_id = getattr(msg, "tool_call_id", None)
    elif isinstance(msg, Mapping):
        # Handle LC serialization: {"type": "constructor", "kwargs": {content, type, ...}}
        kwargs = msg.get("kwargs", {}) if msg.get("type") == "constructor" else msg
        if not isinstance(kwargs, Mapping):
            kwargs = msg
        content = kwargs.get("content", "") or msg.get("content", "")
        tool_calls = kwargs.get("tool_calls") or msg.get("tool_calls")
        msg_type = kwargs.get("type", "") or msg.get("type", "")
        tool_call_id = kwargs.get("tool_call_id") or msg.get("tool_call_id")
    else:
        return parts

    # Tool response (from ToolMessage) — handle before text to avoid double-counting
    if msg_type == "tool":
        response = content if isinstance(content, str) else str(content) if content else ""
        if response or tool_call_id:
            parts.append(ToolCallResponsePart(id=tool_call_id, response=response))
        return parts

    # Text content
    if content and isinstance(content, str) and content.strip():
        parts.append(TextPart(content=content))

    # Tool calls (from AIMessage.tool_calls)
    if tool_calls and isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, Mapping):
                continue
            name = tc.get("name")
            if not name:
                continue
            args = tc.get("args")
            args_str = None
            if args is not None:
                import json

                try:
                    args_str = json.dumps(args) if not isinstance(args, str) else args
                except (TypeError, ValueError):
                    logger.debug("Failed to serialize tool call args for '%s': %s", name, args)
                    args_str = str(args)

            parts.append(
                ToolCallRequestPart(
                    name=name,
                    id=tc.get("id"),
                    arguments=args_str,
                )
            )

    return parts


def _map_base_message(msg: BaseMessage | Mapping[str, Any]) -> ChatMessage | None:
    """Map a single LangChain message to an A365 ChatMessage."""
    role = _map_role(msg)
    parts = _extract_parts(msg)
    if not parts:
        return None

    name = None
    if isinstance(msg, BaseMessage):
        name = getattr(msg, "name", None)

    return ChatMessage(role=role, parts=parts, name=name)


def _map_to_output_message(
    message_data: BaseMessage | Mapping[str, Any],
    generation: Mapping[str, Any],
) -> OutputMessage | None:
    """Map a LangChain generation to an A365 OutputMessage."""
    role = _map_role(message_data, default=MessageRole.ASSISTANT)
    parts = _extract_parts(message_data)
    if not parts:
        return None

    # Extract finish_reason from generation metadata
    finish_reason = None
    gen_info = generation.get("generation_info")
    if isinstance(gen_info, Mapping):
        finish_reason = gen_info.get("finish_reason")

    return OutputMessage(role=role, parts=parts, finish_reason=finish_reason)

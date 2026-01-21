# Copyright (c) Microsoft. All rights reserved.

# -------------------------------------------------- #
# HELPER FUNCTIONS ###
# -------------------------------------------------- #

from collections.abc import Iterable, Iterator, Mapping
from typing import TYPE_CHECKING, Any, assert_never
from urllib.parse import urlparse

from agents import MCPListToolsSpanData
from agents.tracing import Span
from agents.tracing.span_data import (
    AgentSpanData,
    CustomSpanData,
    FunctionSpanData,
    GenerationSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    ResponseSpanData,
    SpanData,
)
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_CHOICE,
    GEN_AI_EVENT_CONTENT,
    GEN_AI_EXECUTION_PAYLOAD_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_PROVIDER_NAME_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_RESPONSE_FINISH_REASONS_KEY,
    GEN_AI_RESPONSE_ID_KEY,
    GEN_AI_SYSTEM_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_ID_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
    GEN_AI_TOOL_NAME_KEY,
    GEN_AI_USAGE_INPUT_TOKENS_KEY,
    GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
)
from microsoft_agents_a365.observability.core.utils import safe_json_dumps
from opentelemetry.trace import (
    Status,
    StatusCode,
)
from opentelemetry.util.types import AttributeValue

from openai.types.responses import (
    EasyInputMessageParam,
    FunctionTool,
    Response,
    ResponseCustomToolCall,
    ResponseCustomToolCallOutputParam,
    ResponseCustomToolCallParam,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseInputContentParam,
    ResponseInputItemParam,
    ResponseOutputItem,
    ResponseOutputMessage,
    ResponseOutputMessageParam,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseUsage,
    Tool,
)
from openai.types.responses.response_input_item_param import FunctionCallOutput, Message
from openai.types.responses.response_output_message_param import Content

from .constants import (
    GEN_AI_LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING,
    GEN_AI_LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHED_READ,
    GEN_AI_LLM_TOKEN_COUNT_TOTAL,
    GEN_AI_MESSAGE_CONTENT,
    GEN_AI_MESSAGE_CONTENT_TYPE,
    GEN_AI_MESSAGE_CONTENTS,
    GEN_AI_MESSAGE_ROLE,
    GEN_AI_MESSAGE_TOOL_CALL_ID,
    GEN_AI_MESSAGE_TOOL_CALL_NAME,
    GEN_AI_MESSAGE_TOOL_CALLS,
    GEN_AI_SPAN_KIND_AGENT_KEY,
    GEN_AI_SPAN_KIND_CHAIN_KEY,
    GEN_AI_SPAN_KIND_LLM_KEY,
    GEN_AI_SPAN_KIND_TOOL_KEY,
    GEN_AI_TOOL_JSON_SCHEMA,
)


def get_span_name(obj: Span[Any]) -> str:
    if hasattr(data := obj.span_data, "name") and isinstance(name := data.name, str):
        return name
    if isinstance(obj.span_data, HandoffSpanData) and obj.span_data.to_agent:
        return f"handoff to {obj.span_data.to_agent}"
    return obj.span_data.type  # type: ignore[no-any-return]


def get_span_kind(obj: SpanData) -> str:
    if isinstance(obj, AgentSpanData):
        return GEN_AI_SPAN_KIND_AGENT_KEY
    if isinstance(obj, FunctionSpanData):
        return GEN_AI_SPAN_KIND_TOOL_KEY
    if isinstance(obj, GenerationSpanData):
        return GEN_AI_SPAN_KIND_LLM_KEY
    if isinstance(obj, ResponseSpanData):
        return GEN_AI_SPAN_KIND_LLM_KEY
    if isinstance(obj, HandoffSpanData):
        return GEN_AI_SPAN_KIND_TOOL_KEY
    if isinstance(obj, CustomSpanData):
        return GEN_AI_SPAN_KIND_CHAIN_KEY
    if isinstance(obj, GuardrailSpanData):
        return GEN_AI_SPAN_KIND_CHAIN_KEY
    return GEN_AI_SPAN_KIND_CHAIN_KEY


def get_attributes_from_input(
    obj: Iterable[ResponseInputItemParam],
    msg_idx: int = 1,
) -> Iterator[tuple[str, AttributeValue]]:
    for i, item in enumerate(obj, msg_idx):
        prefix = f"{GEN_AI_INPUT_MESSAGES_KEY}.{i}."
        if "type" not in item:
            if "role" in item and "content" in item:
                yield from get_attributes_from_message_param(
                    {  # type: ignore[misc, arg-type]
                        "type": "message",
                        "role": item["role"],  # type: ignore[typeddict-item]
                        "content": item["content"],  # type: ignore[typeddict-item]
                    },
                    prefix,
                )
        elif item["type"] == "message":
            yield from get_attributes_from_message_param(item, prefix)
        elif item["type"] == "function_call":
            yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", "assistant"
            yield from get_attributes_from_response_function_tool_call_param(
                item,
                f"{prefix}{GEN_AI_MESSAGE_TOOL_CALLS}.0.",
            )
        elif item["type"] == "function_call_output":
            yield from get_attributes_from_function_call_output(item, prefix)
        elif item["type"] == "custom_tool_call":
            yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", "assistant"
            yield from get_attributes_from_response_custom_tool_call_param(
                item,
                f"{prefix}{GEN_AI_MESSAGE_TOOL_CALLS}.0.",
            )
        elif item["type"] == "custom_tool_call_output":
            yield from get_attributes_from_response_custom_tool_call_output_param(item, prefix)
        elif TYPE_CHECKING and item["type"] is not None:
            assert_never(item["type"])


def get_attributes_from_message_param(
    obj: EasyInputMessageParam | Message | ResponseOutputMessageParam,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", obj["role"]
    if content := obj.get("content"):
        if isinstance(content, str):
            yield f"{prefix}{GEN_AI_MESSAGE_CONTENT}", content
        elif isinstance(content, list):
            yield from get_attributes_from_message_content_list(content, prefix)


def get_attributes_from_response_function_tool_call_param(
    obj: ResponseFunctionToolCallParam,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_MESSAGE_TOOL_CALL_ID}", obj["call_id"]
    yield f"{prefix}{GEN_AI_MESSAGE_TOOL_CALL_NAME}", obj["name"]
    if obj["arguments"] != "{}":
        yield f"{prefix}{GEN_AI_TOOL_ARGS_KEY}", obj["arguments"]


def get_attributes_from_response_custom_tool_call_param(
    obj: ResponseCustomToolCallParam,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    if (call_id := obj.get("call_id")) is not None:
        yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", call_id
    if (name := obj.get("name")) is not None:
        yield f"{prefix}{GEN_AI_TOOL_NAME_KEY}", name
    if (input_data := obj.get("input")) is not None:
        yield (
            f"{prefix}{GEN_AI_TOOL_ARGS_KEY}",
            safe_json_dumps({"input": input_data}),
        )


def get_attributes_from_response_custom_tool_call_output_param(
    obj: ResponseCustomToolCallOutputParam,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", "tool"
    if (call_id := obj.get("call_id")) is not None:
        yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", call_id
    if (output := obj.get("output")) is not None:
        yield f"{prefix}{GEN_AI_TOOL_CALL_RESULT_KEY}", output


def get_attributes_from_function_call_output(
    obj: FunctionCallOutput,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", "tool"
    yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", obj["call_id"]
    yield f"{prefix}{GEN_AI_TOOL_CALL_RESULT_KEY}", obj["output"]


def get_attributes_from_generation_span_data(
    obj: GenerationSpanData,
) -> Iterator[tuple[str, AttributeValue]]:
    yield GEN_AI_PROVIDER_NAME_KEY, "openai"
    if isinstance(model := obj.model, str):
        yield GEN_AI_REQUEST_MODEL_KEY, model
    if isinstance(obj.model_config, dict) and (
        param := {k: v for k, v in obj.model_config.items() if v is not None}
    ):
        yield GEN_AI_EXECUTION_PAYLOAD_KEY, safe_json_dumps(param)
        if base_url := param.get("base_url"):
            parsed = urlparse(base_url)
            if parsed.hostname == "api.openai.com":
                yield GEN_AI_SYSTEM_KEY, "openai"
    yield from _get_attributes_from_chat_completions_input(obj.input)
    yield from _get_attributes_from_chat_completions_output(obj.output)
    yield from _get_attributes_from_chat_completions_usage(obj.usage)


def get_attributes_from_mcp_list_tool_span_data(
    obj: MCPListToolsSpanData,
) -> Iterator[tuple[str, AttributeValue]]:
    yield GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(obj.result)


def _get_attributes_from_chat_completions_input(
    obj: Iterable[Mapping[str, Any]] | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not obj:
        return
    try:
        yield GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps(obj)
    except Exception:
        pass
    yield from get_attributes_from_chat_completions_message_dicts(
        obj,
        f"{GEN_AI_INPUT_MESSAGES_KEY}.",
    )


def _get_attributes_from_chat_completions_output(
    obj: Iterable[Mapping[str, Any]] | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not obj:
        return
    try:
        yield GEN_AI_OUTPUT_MESSAGES_KEY, safe_json_dumps(obj)
    except Exception:
        pass

    if isinstance(obj, Mapping) and "id" in obj:
        yield GEN_AI_RESPONSE_ID_KEY, obj["id"]

    # Collect all finish_reason values
    finish_reasons = [
        message.get("finish_reason") for message in obj if message.get("finish_reason") is not None
    ]
    if finish_reasons:
        yield GEN_AI_RESPONSE_FINISH_REASONS_KEY, ",".join(finish_reasons)

    yield from get_attributes_from_chat_completions_message_dicts(
        obj,
        f"{GEN_AI_OUTPUT_MESSAGES_KEY}.",
    )


def get_attributes_from_chat_completions_message_dicts(
    obj: Iterable[Mapping[str, Any]],
    prefix: str = "",
    msg_idx: int = 0,
    tool_call_idx: int = 0,
) -> Iterator[tuple[str, AttributeValue]]:
    if not isinstance(obj, Iterable):
        return
    for msg in obj:
        if isinstance(role := msg.get("role"), str):
            yield f"{prefix}{msg_idx}.{GEN_AI_MESSAGE_ROLE}", role
        if content := msg.get("content"):
            yield from get_attributes_from_chat_completions_message_content(
                content,
                f"{prefix}{msg_idx}.",
            )
        if isinstance(tool_call_id := msg.get("tool_call_id"), str):
            yield f"{prefix}{msg_idx}.{GEN_AI_MESSAGE_TOOL_CALL_ID}", tool_call_id
        if isinstance(tool_calls := msg.get("tool_calls"), Iterable):
            for tc in tool_calls:
                yield from _get_attributes_from_chat_completions_tool_call_dict(
                    tc,
                    f"{prefix}{msg_idx}.{GEN_AI_MESSAGE_TOOL_CALLS}.{tool_call_idx}.",
                )
                tool_call_idx += 1
        msg_idx += 1


def get_attributes_from_chat_completions_message_content(
    obj: str | Iterable[Mapping[str, Any]],
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    if isinstance(obj, str):
        yield f"{prefix}{GEN_AI_MESSAGE_CONTENT}", obj
    elif isinstance(obj, Iterable):
        for i, item in enumerate(obj):
            if not isinstance(item, Mapping):
                continue
            yield from _get_attributes_from_chat_completions_message_content_item(
                item,
                f"{prefix}{GEN_AI_MESSAGE_CONTENTS}.{i}.",
            )


def _get_attributes_from_chat_completions_message_content_item(
    obj: Mapping[str, Any],
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    if obj.get("type") == "text" and (text := obj.get("text")):
        yield f"{prefix}{GEN_AI_OUTPUT_MESSAGES_KEY}", text


def _get_attributes_from_chat_completions_tool_call_dict(
    obj: Mapping[str, Any],
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    if id_ := obj.get("id"):
        yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", id_
    if function := obj.get("function"):
        if name := function.get("name"):
            yield f"{prefix}{GEN_AI_TOOL_NAME_KEY}", name
        if arguments := function.get("arguments"):
            if arguments != "{}":
                yield f"{prefix}{GEN_AI_TOOL_ARGS_KEY}", arguments


def _get_attributes_from_chat_completions_usage(
    obj: Mapping[str, Any] | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not obj:
        return
    if input_tokens := obj.get("input_tokens"):
        yield GEN_AI_USAGE_INPUT_TOKENS_KEY, input_tokens
    if output_tokens := obj.get("output_tokens"):
        yield GEN_AI_USAGE_OUTPUT_TOKENS_KEY, output_tokens


def _convert_to_primitive(value: Any) -> bool | str | bytes | int | float:
    if isinstance(value, (bool, str, bytes, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return safe_json_dumps(value)
    if isinstance(value, dict):
        return safe_json_dumps(value)
    return str(value)


def get_attributes_from_function_span_data(
    obj: FunctionSpanData,
) -> Iterator[tuple[str, AttributeValue]]:
    yield GEN_AI_TOOL_NAME_KEY, obj.name
    if obj.input:
        yield GEN_AI_TOOL_ARGS_KEY, obj.input
    if obj.output is not None:
        yield GEN_AI_EVENT_CONTENT, _convert_to_primitive(obj.output)


def get_attributes_from_message_content_list(
    obj: Iterable[ResponseInputContentParam | Content],
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    for i, item in enumerate(obj):
        if item["type"] == "input_text" or item["type"] == "output_text":
            yield f"{prefix}{GEN_AI_INPUT_MESSAGES_KEY}.{i}.{GEN_AI_MESSAGE_CONTENT_TYPE}", "text"
            yield (
                f"{prefix}{GEN_AI_INPUT_MESSAGES_KEY}.{i}.{GEN_AI_OUTPUT_MESSAGES_KEY}",
                item["text"],
            )
        elif item["type"] == "refusal":
            yield f"{prefix}{GEN_AI_INPUT_MESSAGES_KEY}.{i}.{GEN_AI_MESSAGE_CONTENT_TYPE}", "text"
            yield (
                f"{prefix}{GEN_AI_INPUT_MESSAGES_KEY}.{i}.{GEN_AI_OUTPUT_MESSAGES_KEY}",
                item["refusal"],
            )
        elif TYPE_CHECKING:
            assert_never(item["type"])


def get_attributes_from_response(obj: Response) -> Iterator[tuple[str, AttributeValue]]:
    yield from get_attributes_from_tools(obj.tools)
    yield from get_attributes_from_usage(obj.usage)
    yield from get_attributes_from_response_output(obj.output)
    if isinstance(obj.instructions, str):
        yield from _get_attributes_from_response_instruction(obj.instructions)
    else:
        pass  # TODO: handle list instructions
    yield GEN_AI_REQUEST_MODEL_KEY, obj.model
    param = obj.model_dump(
        exclude_none=True,
        exclude={"object", "tools", "usage", "output", "error", "status"},
    )
    yield GEN_AI_EXECUTION_PAYLOAD_KEY, safe_json_dumps(param)


def get_attributes_from_tools(
    tools: Iterable[Tool] | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not tools:
        return
    for i, tool in enumerate(tools):
        if isinstance(tool, FunctionTool):
            yield (
                f"{GEN_AI_CHOICE}.{i}.{GEN_AI_TOOL_JSON_SCHEMA}",
                safe_json_dumps(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                            "strict": tool.strict,
                        },
                    }
                ),
            )
        else:
            pass


def get_attributes_from_response_output(
    obj: Iterable[ResponseOutputItem],
    msg_idx: int = 0,
) -> Iterator[tuple[str, AttributeValue]]:
    tool_call_idx = 0
    for _i, item in enumerate(obj):
        if item.type == "message":
            prefix = f"{GEN_AI_OUTPUT_MESSAGES_KEY}.{msg_idx}."
            yield from _get_attributes_from_message(item, prefix)
            msg_idx += 1
        elif item.type == "function_call":
            yield f"{GEN_AI_OUTPUT_MESSAGES_KEY}.{msg_idx}.{GEN_AI_MESSAGE_ROLE}", "assistant"
            prefix = f"{GEN_AI_OUTPUT_MESSAGES_KEY}.{msg_idx}.{GEN_AI_MESSAGE_TOOL_CALLS}.{tool_call_idx}."
            yield from _get_attributes_from_function_tool_call(item, prefix)
            tool_call_idx += 1
        elif item.type == "custom_tool_call":
            yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", "assistant"
            yield from _get_attributes_from_response_custom_tool_call(
                item,
                f"{prefix}{GEN_AI_MESSAGE_TOOL_CALLS}.0.",
            )
        elif TYPE_CHECKING:
            assert_never(item)


def _get_attributes_from_response_instruction(
    instructions: str | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not instructions:
        return
    yield f"{GEN_AI_INPUT_MESSAGES_KEY}.0.{GEN_AI_MESSAGE_ROLE}", "system"
    yield f"{GEN_AI_INPUT_MESSAGES_KEY}.0.{GEN_AI_OUTPUT_MESSAGES_KEY}", instructions


def _get_attributes_from_function_tool_call(
    obj: ResponseFunctionToolCall,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", obj.call_id
    yield f"{prefix}{GEN_AI_TOOL_NAME_KEY}", obj.name
    if obj.arguments != "{}":
        yield f"{prefix}{GEN_AI_TOOL_ARGS_KEY}", obj.arguments


def _get_attributes_from_response_custom_tool_call(
    obj: ResponseCustomToolCall,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    if (call_id := obj.call_id) is not None:
        yield f"{prefix}{GEN_AI_TOOL_CALL_ID_KEY}", call_id
    if (name := obj.name) is not None:
        yield f"{prefix}{GEN_AI_TOOL_NAME_KEY}", name
    if (input_data := obj.input) is not None:
        yield (
            f"{prefix}{GEN_AI_TOOL_ARGS_KEY}",
            safe_json_dumps({"input": input_data}),
        )


def _get_attributes_from_message(
    obj: ResponseOutputMessage,
    prefix: str = "",
) -> Iterator[tuple[str, AttributeValue]]:
    yield f"{prefix}{GEN_AI_MESSAGE_ROLE}", obj.role
    for i, item in enumerate(obj.content):
        if isinstance(item, ResponseOutputText):
            yield f"{prefix}{GEN_AI_OUTPUT_MESSAGES_KEY}.{i}.{GEN_AI_MESSAGE_CONTENT_TYPE}", "text"
            yield (
                f"{prefix}{GEN_AI_OUTPUT_MESSAGES_KEY}.{i}.{GEN_AI_OUTPUT_MESSAGES_KEY}",
                item.text,
            )
        elif isinstance(item, ResponseOutputRefusal):
            yield f"{prefix}{GEN_AI_OUTPUT_MESSAGES_KEY}.{i}.{GEN_AI_MESSAGE_CONTENT_TYPE}", "text"
            yield (
                f"{prefix}{GEN_AI_OUTPUT_MESSAGES_KEY}.{i}.{GEN_AI_OUTPUT_MESSAGES_KEY}",
                item.refusal,
            )
        elif TYPE_CHECKING:
            assert_never(item)


def get_attributes_from_usage(
    obj: ResponseUsage | None,
) -> Iterator[tuple[str, AttributeValue]]:
    if not obj:
        return
    yield GEN_AI_USAGE_OUTPUT_TOKENS_KEY, obj.output_tokens
    yield GEN_AI_USAGE_INPUT_TOKENS_KEY, obj.input_tokens
    yield GEN_AI_LLM_TOKEN_COUNT_TOTAL, obj.total_tokens
    yield GEN_AI_LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHED_READ, obj.input_tokens_details.cached_tokens
    yield (
        GEN_AI_LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING,
        obj.output_tokens_details.reasoning_tokens,
    )


def get_span_status(obj: Span[Any]) -> Status:
    if error := getattr(obj, "error", None):
        return Status(
            status_code=StatusCode.ERROR, description=f"{error.get('message')}: {error.get('data')}"
        )
    else:
        return Status(StatusCode.OK)


def capture_tool_call_ids(
    output_list: Any, pending_tool_calls: dict[str, str], max_size: int = 1000
) -> None:
    """Extract and store tool_call_ids from generation output for later use by FunctionSpan.

    Args:
        output_list: The generation output containing tool calls
        pending_tool_calls: OrderedDict to store pending tool calls
        max_size: Maximum number of pending tool calls to keep in memory
    """
    if not output_list:
        return
    try:
        for msg in output_list:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            call_id = tc.get("id")
                            func = tc.get("function", {})
                            func_name = func.get("name") if isinstance(func, dict) else None
                            func_args = func.get("arguments", "") if isinstance(func, dict) else ""
                            if call_id and func_name:
                                # Key by (function_name, arguments) to uniquely identify each call
                                key = f"{func_name}:{func_args}"
                                pending_tool_calls[key] = call_id
                                # Cap the size of the dict to prevent unbounded growth
                                while len(pending_tool_calls) > max_size:
                                    pending_tool_calls.popitem(last=False)
    except Exception:
        pass


def get_tool_call_id(
    function_name: str, function_args: str, pending_tool_calls: dict[str, str]
) -> str | None:
    """Get and remove the tool_call_id for a function with specific arguments."""
    key = f"{function_name}:{function_args}"
    return pending_tool_calls.pop(key, None)


def capture_input_message(
    parent_span_id: str, input_list: Any, agent_inputs: dict[str, str]
) -> None:
    """Extract and store the first user message from input list for parent agent span."""
    if parent_span_id in agent_inputs:
        return  # Already captured
    if not input_list:
        return
    try:
        for msg in input_list:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    agent_inputs[parent_span_id] = str(content)
                    return
    except Exception:
        pass


def capture_output_message(
    parent_span_id: str, output_list: Any, agent_outputs: dict[str, str]
) -> None:
    """Extract and store the last assistant message with actual content (no tool calls) for parent agent span."""
    if not output_list:
        return
    try:
        # Iterate in reverse to get the last assistant message with content (not a tool call)
        output_items = list(output_list) if not isinstance(output_list, list) else output_list
        for msg in reversed(output_items):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")
                # Only capture if there's actual content and no tool_calls
                # (tool_calls means this is an intermediate step, not the final response)
                if content and not tool_calls:
                    agent_outputs[parent_span_id] = str(content)
                    return
    except Exception:
        pass


def find_ancestor_agent_span_id(
    span_id: str | None, agent_span_ids: set[str], span_parents: dict[str, str]
) -> str | None:
    """Walk up the parent chain to find the nearest ancestor AgentSpan."""
    current = span_id
    visited: set[str] = set()  # Prevent infinite loops
    while current and current not in visited:
        if current in agent_span_ids:
            return current
        visited.add(current)
        current = span_parents.get(current)
    return None

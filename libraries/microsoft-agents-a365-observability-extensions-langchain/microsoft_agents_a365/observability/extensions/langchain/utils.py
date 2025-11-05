# Copyright (c) Microsoft. All rights reserved.

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.tracers.schemas import Run
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_PROVIDER_NAME_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_RESPONSE_FINISH_REASONS_KEY,
    GEN_AI_RESPONSE_ID_KEY,
    GEN_AI_SYSTEM_INSTRUCTIONS_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_ID_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
    GEN_AI_TOOL_DESCRIPTION_KEY,
    GEN_AI_TOOL_NAME_KEY,
    GEN_AI_TOOL_TYPE_KEY,
    GEN_AI_USAGE_INPUT_TOKENS_KEY,
    GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
    SESSION_ID_KEY,
)
from microsoft_agents_a365.observability.core.inference_operation_type import InferenceOperationType
from microsoft_agents_a365.observability.core.utils import (
    get_first_value,
    safe_json_dumps,
    stop_on_exception,
)

IGNORED_EXCEPTION_PATTERNS = [
    r"^Command\(",
    r"^ParentCommand\(",
]

LANGCHAIN_SESSION_ID = "session_id"
LANGCHAIN_CONVERSATION_ID = "conversation_id"
LANGCHAIN_THREAD_ID = "thread_id"


@stop_on_exception
def prompts(inputs: Mapping[str, Any] | None) -> Iterator[tuple[str, list[str]]]:
    """Yields prompts if present."""
    if not inputs:
        return
    assert hasattr(inputs, "get"), f"expected Mapping, found {type(inputs)}"
    if prompts := inputs.get("prompts"):
        yield GEN_AI_SYSTEM_INSTRUCTIONS_KEY, prompts


@stop_on_exception
def _extract_message_kwargs(message_data: Mapping[str, Any] | None) -> Iterator[[str, Any]]:
    if not message_data:
        return
    assert hasattr(message_data, "get"), f"expected Mapping, found {type(message_data)}"
    if kwargs := message_data.get("kwargs"):
        assert hasattr(kwargs, "get"), f"expected Mapping, found {type(kwargs)}"
        if content := kwargs.get("content"):
            # Just yield as-is (string or list)
            yield "message.content", content
        if tool_call_id := kwargs.get("tool_call_id"):
            assert isinstance(tool_call_id, str), f"expected str, found {type(tool_call_id)}"
            yield GEN_AI_TOOL_CALL_ID_KEY, tool_call_id
        if name := kwargs.get("name"):
            assert isinstance(name, str), f"expected str, found {type(name)}"
            yield "message.name", name


@stop_on_exception
def _extract_message_additional_kwargs(
    message_data: Mapping[str, Any] | None,
) -> Iterator[tuple[str, Any]]:
    if not message_data:
        return
    assert hasattr(message_data, "get"), f"expected Mapping, found {type(message_data)}"
    if kwargs := message_data.get("kwargs"):
        assert hasattr(kwargs, "get"), f"expected Mapping, found {type(kwargs)}"
        if additional_kwargs := kwargs.get("additional_kwargs"):
            assert hasattr(additional_kwargs, "get"), (
                f"expected Mapping, found {type(additional_kwargs)}"
            )
            if function_call := additional_kwargs.get("function_call"):
                assert hasattr(function_call, "get"), (
                    f"expected Mapping, found {type(function_call)}"
                )
                if name := function_call.get("name"):
                    assert isinstance(name, str), f"expected str, found {type(name)}"
                    yield GEN_AI_TOOL_NAME_KEY, name
                if arguments := function_call.get("arguments"):
                    if isinstance(arguments, str):
                        yield GEN_AI_TOOL_ARGS_KEY, arguments
                    else:
                        yield GEN_AI_TOOL_ARGS_KEY, safe_json_dumps(arguments)


@stop_on_exception
def _get_tool_call(tool_call: Mapping[str, Any] | None) -> Iterator[tuple[str, Any]]:
    if not tool_call:
        return
    assert hasattr(tool_call, "get"), f"expected Mapping, found {type(tool_call)}"

    # id
    id_ = tool_call.get("id")
    if id_ is not None:
        yield GEN_AI_TOOL_CALL_ID_KEY, id_

    fn = tool_call.get("function")
    name = None
    arguments = None

    if hasattr(fn, "get"):
        name = fn.get("name")
        arguments = fn.get("arguments")
    else:
        name = tool_call.get("name")
        arguments = tool_call.get("args")

    # name
    if name is not None:
        assert isinstance(name, str), f"expected str, found {type(name)}"
        yield GEN_AI_TOOL_NAME_KEY, name

    # arguments -> always emit a JSON string
    if arguments is not None:
        if isinstance(arguments, str):
            args_json = arguments
        else:
            args_json = safe_json_dumps(arguments)
        yield GEN_AI_TOOL_ARGS_KEY, args_json


def _process_tool_calls(tool_calls: Any) -> str:
    """Return all tool calls as a single compact string (JSON-joined), or '' if none."""
    if not tool_calls:
        return ""
    assert isinstance(tool_calls, Iterable), f"expected Iterable, found {type(tool_calls)}"

    parts: list[str] = []
    for tool_call in tool_calls:
        data = dict(_get_tool_call(tool_call))
        if data:
            # Compact, stable representation
            parts.append(safe_json_dumps(data, separators=(",", ":"), sort_keys=True))

    return "; ".join(parts)


@stop_on_exception
def _extract_message_tool_calls(
    message_data: Mapping[str, Any] | None,
) -> Iterator[tuple[str, str]]:
    if not message_data:
        return
    assert hasattr(message_data, "get"), f"expected Mapping, found {type(message_data)}"

    # Collect tool_calls from multiple possible locations
    all_tool_calls: list[str] = []

    def collect(calls: Any) -> None:
        if calls:
            processed = _process_tool_calls(calls)
            if processed:
                if isinstance(processed, list):
                    all_tool_calls.extend(map(str, processed))
                else:
                    all_tool_calls.append(str(processed))

    collect(message_data.get("tool_calls"))

    if kwargs := message_data.get("kwargs"):
        assert hasattr(kwargs, "get"), f"expected Mapping, found {type(kwargs)}"
        collect(kwargs.get("tool_calls"))

        if additional_kwargs := kwargs.get("additional_kwargs"):
            assert hasattr(additional_kwargs, "get"), (
                f"expected Mapping, found {type(additional_kwargs)}"
            )
            collect(additional_kwargs.get("tool_calls"))

    if all_tool_calls:
        # Return all as a single string (comma-separated)
        yield "message.tool_calls", ", ".join(all_tool_calls)


@stop_on_exception
def _parse_message_data(message_data: Mapping[str, Any] | None) -> Iterator[tuple[str, Any]]:
    """Parses message data to grab message role, content, etc."""
    yield from _extract_message_kwargs(message_data)
    yield from _extract_message_additional_kwargs(message_data)
    yield from _extract_message_tool_calls(message_data)


@stop_on_exception
def input_messages(
    inputs: Mapping[str, Any] | None,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Yields chat messages if present."""
    if not inputs:
        return
    assert hasattr(inputs, "get"), f"expected Mapping, found {type(inputs)}"
    # There may be more than one set of messages. We'll use just the first set.
    if not (multiple_messages := inputs.get("messages")):
        return
    assert isinstance(multiple_messages, Iterable), (
        f"expected Iterable, found {type(multiple_messages)}"
    )
    # This will only get the first set of messages.
    if not (first_messages := next(iter(multiple_messages), None)):
        return
    parsed_messages = []
    if isinstance(first_messages, list):
        for message_data in first_messages:
            if isinstance(message_data, BaseMessage):
                parsed_messages.append(dict(_parse_message_data(message_data.to_json())))
            elif hasattr(message_data, "get"):
                parsed_messages.append(dict(_parse_message_data(message_data)))
            else:
                raise ValueError(f"failed to parse message of type {type(message_data)}")
    elif isinstance(first_messages, BaseMessage):
        parsed_messages.append(dict(_parse_message_data(first_messages.to_json())))
    elif hasattr(first_messages, "get"):
        parsed_messages.append(dict(_parse_message_data(first_messages)))
    elif isinstance(first_messages, Sequence) and len(first_messages) == 2:
        # See e.g. https://github.com/langchain-ai/langchain/blob/18cf457eec106d99e0098b42712299f5d0daa798/libs/core/langchain_core/messages/utils.py#L317  # noqa: E501
        role, content = first_messages
        parsed_messages.append({"MESSAGE_ROLE": role, "MESSAGE_CONTENT": content})
    else:
        raise ValueError(f"failed to parse messages of type {type(first_messages)}")
    if parsed_messages:
        yield GEN_AI_INPUT_MESSAGES_KEY, parsed_messages


@stop_on_exception
def metadata(run: Run) -> Iterator[tuple[str, str]]:
    """
    Takes the LangChain chain metadata and adds it to the trace
    """
    if not run.extra or not (metadata := run.extra.get("metadata")):
        return
    assert isinstance(metadata, Mapping), f"expected Mapping, found {type(metadata)}"
    if session_id := (
        metadata.get(LANGCHAIN_SESSION_ID)
        or metadata.get(LANGCHAIN_CONVERSATION_ID)
        or metadata.get(LANGCHAIN_THREAD_ID)
    ):
        yield SESSION_ID_KEY, session_id


@stop_on_exception
def output_messages(
    outputs: Mapping[str, Any] | None,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Yields chat messages if present."""
    if not outputs:
        return
    assert hasattr(outputs, "get"), f"expected Mapping, found {type(outputs)}"
    output_type = outputs.get("type")
    if output_type and output_type.lower() == "llmresult":
        llm_output = outputs.get("llm_output")
        if llm_output and hasattr(llm_output, "get"):
            response_id = llm_output.get("id")
            if response_id:
                yield GEN_AI_RESPONSE_ID_KEY, response_id
    # There may be more than one set of generations. We'll use just the first set.
    if not (multiple_generations := outputs.get("generations")):
        return
    assert isinstance(multiple_generations, Iterable), (
        f"expected Iterable, found {type(multiple_generations)}"
    )
    # This will only get the first set of generations.
    if not (first_generations := next(iter(multiple_generations), None)):
        return
    assert isinstance(first_generations, Iterable), (
        f"expected Iterable, found {type(first_generations)}"
    )
    parsed_messages = []
    for generation in first_generations:
        assert hasattr(generation, "get"), f"expected Mapping, found {type(generation)}"
        if message_data := generation.get("message"):
            if isinstance(message_data, BaseMessage):
                parsed_messages.append(dict(_parse_message_data(message_data.to_json())))
            elif hasattr(message_data, "get"):
                parsed_messages.append(dict(_parse_message_data(message_data)))
            else:
                raise ValueError(f"fail to parse message of type {type(message_data)}")
    if parsed_messages:
        yield GEN_AI_OUTPUT_MESSAGES_KEY, parsed_messages


@stop_on_exception
def invocation_parameters(run: Run) -> Iterator[tuple[str, str]]:
    """Yields invocation parameters if present."""
    if run.run_type.lower() != "llm":
        return
    if not (extra := run.extra):
        return
    assert hasattr(extra, "get"), f"expected Mapping, found {type(extra)}"
    if invocation_parameters := extra.get("invocation_params"):
        assert isinstance(invocation_parameters, Mapping), (
            f"expected Mapping, found {type(invocation_parameters)}"
        )
        yield GEN_AI_INPUT_MESSAGES_KEY, safe_json_dumps(invocation_parameters)
        tools = invocation_parameters.get("tools", [])
        for idx, tool in enumerate(tools):
            yield f"{GEN_AI_TOOL_ARGS_KEY}.{idx}", safe_json_dumps(tool)


@stop_on_exception
def llm_provider(extra: Mapping[str, Any] | None) -> Iterator[tuple[str, str]]:
    if not extra:
        return
    if (meta := extra.get("metadata")) and (ls_provider := meta.get("ls_provider")):
        ls_provider_lower = ls_provider.lower()
        yield GEN_AI_PROVIDER_NAME_KEY, ls_provider_lower


@stop_on_exception
def model_name(
    outputs: Mapping[str, Any] | None,
    extra: Mapping[str, Any] | None,
) -> Iterator[tuple[str, str]]:
    """Yields model name if present."""
    if (
        outputs
        and hasattr(outputs, "get")
        and (llm_output := outputs.get("llm_output"))
        and hasattr(llm_output, "get")
    ):
        for key in "model_name", "model":
            if name := str(llm_output.get(key) or "").strip():
                yield GEN_AI_REQUEST_MODEL_KEY, name
                return
    if not extra:
        return
    assert hasattr(extra, "get"), f"expected Mapping, found {type(extra)}"
    if (
        (metadata := extra.get("metadata"))
        and hasattr(metadata, "get")
        and (ls_model_name := str(metadata.get("ls_model_name") or "").strip())
    ):
        yield GEN_AI_REQUEST_MODEL_KEY, ls_model_name
        return
    if not (invocation_params := extra.get("invocation_params")):
        return
    for key in ["model_name", "model"]:
        if name := invocation_params.get(key):
            yield GEN_AI_REQUEST_MODEL_KEY, name
            return


@stop_on_exception
def token_counts(outputs: Mapping[str, Any] | None) -> Iterator[tuple[str, int]]:
    """Yields token count information if present."""
    if not (token_usage := (parse_token_usage_for_non_streaming_outputs(outputs))):
        return
    for attribute_name, keys in [
        (
            GEN_AI_USAGE_INPUT_TOKENS_KEY,
            (
                "prompt_tokens",
                "input_tokens",  # Anthropic-specific key
                "prompt_token_count",  # Gemini-specific key - https://ai.google.dev/gemini-api/docs/tokens?lang=python
            ),
        ),
        (
            GEN_AI_USAGE_OUTPUT_TOKENS_KEY,
            (
                "completion_tokens",
                "output_tokens",  # Anthropic-specific key
                "candidates_token_count",  # Gemini-specific key
            ),
        ),
    ]:
        if (token_count := get_first_value(token_usage, keys)) is not None:
            yield attribute_name, token_count

    # OpenAI
    for attribute_name, details_key, keys in [
        (
            GEN_AI_RESPONSE_FINISH_REASONS_KEY,
            "completion_tokens_details",
            ("reasoning_tokens",),
        ),
    ]:
        if (details := token_usage.get(details_key)) is not None:
            if (token_count := get_first_value(details, keys)) is not None:
                yield attribute_name, token_count

    # maps langchain_core.messages.ai.UsageMetadata object
    for attribute_name, details_key_or_none, keys in [
        (GEN_AI_USAGE_INPUT_TOKENS_KEY, None, ("input_tokens",)),
        (GEN_AI_USAGE_OUTPUT_TOKENS_KEY, None, ("output_tokens",)),
        (
            GEN_AI_RESPONSE_FINISH_REASONS_KEY,
            "output_token_details",
            ("reasoning",),
        ),
    ]:
        details = token_usage.get(details_key_or_none) if details_key_or_none else token_usage
        if details is not None:
            if (token_count := get_first_value(details, keys)) is not None:
                yield attribute_name, token_count


def parse_token_usage_for_non_streaming_outputs(
    outputs: Mapping[str, Any] | None,
) -> Any:
    """
    Parses output to get token usage information for non-streaming LLMs, i.e.,
    when `stream_usage` is set to false.
    """
    if (
        outputs
        and hasattr(outputs, "get")
        and (llm_output := outputs.get("llm_output"))
        and hasattr(llm_output, "get")
        and (
            token_usage := get_first_value(
                llm_output,
                (
                    "token_usage",
                    "usage",  # Anthropic-specific key
                ),
            )
        )
    ):
        return token_usage
    return None


@stop_on_exception
def function_calls(outputs: Mapping[str, Any] | None) -> Iterator[tuple[str, str]]:
    """
    Extract a single OpenAI-style function call from model outputs and emit
    GenAI tool attributes as (key, value) pairs. Arguments/result are JSON strings.

    """
    if not outputs:
        return
    assert hasattr(outputs, "get"), f"expected Mapping, found {type(outputs)}"

    try:
        # Typical OpenAI LangChain shape:
        # outputs["generations"][0][0]["message"]["kwargs"]["additional_kwargs"]["function_call"]
        fc = deepcopy(
            outputs["generations"][0][0]["message"]["kwargs"]["additional_kwargs"]["function_call"]
        )
    except Exception:
        return

    if not isinstance(fc, dict):
        return

    # Tool type (explicit)
    yield GEN_AI_OPERATION_NAME_KEY, "execute_tool"
    yield GEN_AI_TOOL_TYPE_KEY, "function"

    name = fc.get("name")
    if isinstance(name, str):
        yield GEN_AI_TOOL_NAME_KEY, name

    desc = fc.get("description")
    if isinstance(desc, str):
        yield GEN_AI_TOOL_DESCRIPTION_KEY, desc

    call_id = fc.get("id")
    if isinstance(call_id, str):
        yield GEN_AI_TOOL_CALL_ID_KEY, call_id

    args = fc.get("arguments")
    if args is not None:
        if isinstance(args, str):
            # If it's a JSON string, try to parse then re-dump for normalization
            try:
                args_json = safe_json_dumps(json.loads(args))
            except Exception:
                # Not valid JSON; store raw string
                args_json = safe_json_dumps(args)
        else:
            args_json = safe_json_dumps(args)
        yield GEN_AI_TOOL_ARGS_KEY, args_json

    result = fc.get("result")
    if result is not None:
        yield GEN_AI_TOOL_CALL_RESULT_KEY, safe_json_dumps(result)


@stop_on_exception
def tools(run: Run) -> Iterator[tuple[str, str]]:
    """Yields tool attributes if present."""
    if run.run_type.lower() != "tool":
        return
    if not (serialized := run.serialized):
        return
    assert hasattr(serialized, "get"), f"expected Mapping, found {type(serialized)}"
    yield GEN_AI_TOOL_TYPE_KEY, "extension"
    if name := serialized.get("name"):
        yield GEN_AI_TOOL_NAME_KEY, name
    if description := serialized.get("description"):
        yield GEN_AI_TOOL_DESCRIPTION_KEY, description


def add_operation_type(run: Run) -> Iterator[tuple[str, str]]:
    """Yields operation type based on run type."""
    run_type = run.run_type.lower()
    if run_type == "llm":
        yield GEN_AI_OPERATION_NAME_KEY, InferenceOperationType.CHAT.value.lower()
    elif run_type == "chat_model":
        yield GEN_AI_OPERATION_NAME_KEY, "chat"
    elif run_type == "tool":
        yield GEN_AI_OPERATION_NAME_KEY, "execute_tool"

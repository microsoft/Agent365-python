# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for the OpenAI message mapper."""

import json

from microsoft_agents_a365.observability.extensions.openai.message_mapper import (
    map_input_messages,
    map_output_messages,
)


class TestMapInputMessages:
    """Tests for map_input_messages."""

    def test_empty_string_returns_none(self) -> None:
        assert map_input_messages("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert map_input_messages("   ") is None

    def test_plain_string_wraps_as_user_message(self) -> None:
        result = map_input_messages("Hello world")
        assert result is not None
        data = json.loads(result)

        assert len(data) == 1
        assert data[0]["role"] == "user"
        assert data[0]["parts"][0]["type"] == "text"
        assert data[0]["parts"][0]["content"] == "Hello world"

    def test_chat_completions_format(self) -> None:
        """Standard chat completions format with system + user messages."""
        raw = json.dumps([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi there"},
        ])
        result = map_input_messages(raw)
        assert result is not None
        data = json.loads(result)

        assert len(data) == 2
        assert data[0]["role"] == "system"
        assert data[0]["parts"][0]["content"] == "You are helpful."
        assert data[1]["role"] == "user"
        assert data[1]["parts"][0]["content"] == "Hi there"

    def test_chat_completions_with_tool_calls(self) -> None:
        """Messages with assistant tool_calls and tool response."""
        raw = json.dumps([
            {"role": "user", "content": "What is 2+2?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "function": {"name": "add", "arguments": '{"a":2,"b":2}'},
                    }
                ],
            },
            {"role": "tool", "content": "4", "tool_call_id": "call_123"},
        ])
        result = map_input_messages(raw)
        assert result is not None
        data = json.loads(result)

        assert len(data) == 3

        # User message
        assert data[0]["role"] == "user"
        assert data[0]["parts"][0]["type"] == "text"

        # Assistant with tool call
        assert data[1]["role"] == "assistant"
        assert data[1]["parts"][0]["type"] == "tool_call"
        assert data[1]["parts"][0]["name"] == "add"
        assert data[1]["parts"][0]["id"] == "call_123"

        # Tool response
        assert data[2]["role"] == "tool"
        assert data[2]["parts"][0]["type"] == "tool_call_response"
        assert data[2]["parts"][0]["id"] == "call_123"
        assert data[2]["parts"][0]["response"] == "4"

    def test_response_input_item_param_format(self) -> None:
        """ResponseInputItemParam format with typed items."""
        raw = json.dumps([
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}],
            },
            {
                "type": "function_call",
                "name": "get_weather",
                "call_id": "fc_1",
                "arguments": '{"city":"Seattle"}',
            },
            {"type": "function_call_output", "call_id": "fc_1", "output": "Sunny, 22C"},
        ])
        result = map_input_messages(raw)
        assert result is not None
        data = json.loads(result)

        assert len(data) == 3

        # Message
        assert data[0]["role"] == "user"
        assert data[0]["parts"][0]["type"] == "text"

        # Function call
        assert data[1]["role"] == "assistant"
        assert data[1]["parts"][0]["type"] == "tool_call"
        assert data[1]["parts"][0]["name"] == "get_weather"

        # Function call output
        assert data[2]["role"] == "tool"
        assert data[2]["parts"][0]["type"] == "tool_call_response"
        assert data[2]["parts"][0]["response"] == "Sunny, 22C"

    def test_message_without_type_field(self) -> None:
        """Messages without explicit 'type' field (EasyInputMessageParam)."""
        raw = json.dumps([
            {"role": "user", "content": "Hello"},
        ])
        result = map_input_messages(raw)
        assert result is not None
        data = json.loads(result)
        assert data[0]["role"] == "user"

    def test_invalid_json_wraps_as_plain_text(self) -> None:
        result = map_input_messages("not json {")
        assert result is not None
        data = json.loads(result)

        assert data[0]["parts"][0]["content"] == "not json {"

    def test_empty_list_returns_none(self) -> None:
        assert map_input_messages("[]") is None


class TestMapOutputMessages:
    """Tests for map_output_messages."""

    def test_empty_string_returns_none(self) -> None:
        assert map_output_messages("") is None

    def test_plain_string_wraps_as_assistant(self) -> None:
        result = map_output_messages("The answer is 42.")
        assert result is not None
        data = json.loads(result)

        assert data[0]["role"] == "assistant"
        assert data[0]["parts"][0]["content"] == "The answer is 42."

    def test_chat_completions_output(self) -> None:
        """Standard chat completions output with finish_reason."""
        raw = json.dumps([
            {
                "role": "assistant",
                "content": "Paris is the capital.",
                "finish_reason": "stop",
            }
        ])
        result = map_output_messages(raw)
        assert result is not None
        data = json.loads(result)

        assert len(data) == 1
        msg = data[0]
        assert msg["role"] == "assistant"
        assert msg["parts"][0]["type"] == "text"
        assert msg["parts"][0]["content"] == "Paris is the capital."
        assert msg["finish_reason"] == "stop"

    def test_chat_completions_with_tool_calls(self) -> None:
        """Output with tool_calls."""
        raw = json.dumps([
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "function": {"name": "search", "arguments": '{"q":"test"}'},
                    }
                ],
                "finish_reason": "tool_calls",
            }
        ])
        result = map_output_messages(raw)
        assert result is not None
        data = json.loads(result)
        msg = data[0]
        assert msg["role"] == "assistant"
        assert msg["parts"][0]["type"] == "tool_call"
        assert msg["parts"][0]["name"] == "search"
        assert msg["finish_reason"] == "tool_calls"

    def test_response_json_format(self) -> None:
        """Full OpenAI Response JSON (from model_dump_json)."""
        raw = json.dumps({
            "id": "resp_123",
            "model": "gpt-4o",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello!"}],
                    "status": "completed",
                }
            ],
        })
        result = map_output_messages(raw)
        assert result is not None
        data = json.loads(result)

        msg = data[0]
        assert msg["role"] == "assistant"
        assert msg["parts"][0]["type"] == "text"
        assert msg["parts"][0]["content"] == "Hello!"

    def test_response_json_with_function_call(self) -> None:
        """Response JSON with function_call output item."""
        raw = json.dumps({
            "id": "resp_456",
            "model": "gpt-4o",
            "output": [
                {
                    "type": "function_call",
                    "name": "get_weather",
                    "call_id": "fc_1",
                    "arguments": '{"city":"NYC"}',
                }
            ],
        })
        result = map_output_messages(raw)
        assert result is not None
        data = json.loads(result)
        msg = data[0]
        assert msg["role"] == "assistant"
        assert msg["parts"][0]["type"] == "tool_call"
        assert msg["parts"][0]["name"] == "get_weather"
        assert msg["finish_reason"] == "tool_call"

    def test_response_json_without_output_returns_none(self) -> None:
        """Response JSON without output field."""
        raw = json.dumps({"id": "resp_789", "model": "gpt-4o"})
        assert map_output_messages(raw) is None

    def test_empty_list_returns_none(self) -> None:
        assert map_output_messages("[]") is None

    def test_invalid_json_wraps_as_plain_text(self) -> None:
        result = map_output_messages("bad json")
        assert result is not None
        data = json.loads(result)

        assert data[0]["role"] == "assistant"

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for the LangChain message mapper.

These tests cover mapping behaviour without requiring real Azure credentials.
All LangChain objects are constructed directly so no network calls are made.
"""

import json
import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from microsoft_agents_a365.observability.extensions.langchain.message_mapper import (
    map_input_messages,
    map_output_messages,
)


class TestMapInputMessages(unittest.TestCase):
    """Tests for map_input_messages."""

    def _parse(self, result: str | None) -> dict:
        self.assertIsNotNone(result)
        return json.loads(result)  # type: ignore[arg-type]

    def test_system_message(self) -> None:
        """A system message maps to role=system with a text part."""
        inputs = {"messages": [[SystemMessage(content="You are helpful.")]]}
        data = self._parse(map_input_messages(inputs))
        self.assertEqual(data["version"], "0.1.0")
        msgs = data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "system")
        parts = msgs[0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[0]["content"], "You are helpful.")

    def test_human_message(self) -> None:
        """A human message maps to role=user with a text part."""
        inputs = {"messages": [[HumanMessage(content="Hello!")]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["parts"][0]["content"], "Hello!")

    def test_assistant_message(self) -> None:
        """An AI message maps to role=assistant with a text part."""
        inputs = {"messages": [[AIMessage(content="I can help.")]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        self.assertEqual(msgs[0]["role"], "assistant")
        self.assertEqual(msgs[0]["parts"][0]["content"], "I can help.")

    def test_tool_message(self) -> None:
        """A ToolMessage maps to role=tool with a tool_call_response part."""
        inputs = {"messages": [[ToolMessage(content="42", tool_call_id="call_abc")]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        self.assertEqual(msgs[0]["role"], "tool")
        parts = msgs[0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["type"], "tool_call_response")
        self.assertEqual(parts[0]["id"], "call_abc")
        self.assertEqual(parts[0]["response"], "42")

    def test_tool_call_args_as_dict_kept_structured(self) -> None:
        """When tool-call args are already a dict they stay structured (not stringified)."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search", "id": "call_1", "args": {"query": "hello"}, "type": "tool_use"}
            ],
        )
        inputs = {"messages": [[ai_msg]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        tool_part = next(p for p in msgs[0]["parts"] if p["type"] == "tool_call")
        # arguments must be a dict, not a JSON string
        self.assertIsInstance(tool_part["arguments"], dict)
        self.assertEqual(tool_part["arguments"], {"query": "hello"})

    def test_tool_call_args_as_json_string_parsed(self) -> None:
        """When tool-call args arrive as a JSON string they are parsed to a dict.

        LangChain ``AIMessage.tool_calls`` enforces dict args via pydantic, so
        this scenario is exercised via the Mapping path of ``_extract_parts``.
        """
        # Simulate a serialized LangChain message where args is a JSON string
        msg_mapping = {
            "type": "ai",
            "content": "",
            "tool_calls": [{"name": "search", "id": "call_2", "args": '{"query": "world"}'}],
        }
        inputs = {"messages": [[msg_mapping]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        tool_part = next(p for p in msgs[0]["parts"] if p["type"] == "tool_call")
        # Must be parsed to a dict
        self.assertIsInstance(tool_part["arguments"], dict)
        self.assertEqual(tool_part["arguments"]["query"], "world")

    def test_tool_call_args_invalid_json_string_kept_as_string(self) -> None:
        """When tool-call args are an un-parseable string they are kept as-is.

        Uses the Mapping path of ``_extract_parts`` (same reason as above).
        """
        msg_mapping = {
            "type": "ai",
            "content": "",
            "tool_calls": [{"name": "search", "id": "call_3", "args": "not-valid-json"}],
        }
        inputs = {"messages": [[msg_mapping]]}
        data = self._parse(map_input_messages(inputs))
        msgs = data["messages"]
        tool_part = next(p for p in msgs[0]["parts"] if p["type"] == "tool_call")
        self.assertEqual(tool_part["arguments"], "not-valid-json")

    def test_empty_content_ignored(self) -> None:
        """Messages with empty or whitespace-only content produce no text part."""
        ai_msg = AIMessage(content="   ")
        inputs = {"messages": [[ai_msg]]}
        result = map_input_messages(inputs)
        # No text part → message filtered → None returned
        self.assertIsNone(result)

    def test_none_inputs_returns_none(self) -> None:
        """None inputs return None without error."""
        self.assertIsNone(map_input_messages(None))

    def test_empty_dict_returns_none(self) -> None:
        """Empty inputs dict returns None."""
        self.assertIsNone(map_input_messages({}))

    def test_multiple_messages_in_sequence(self) -> None:
        """Multiple messages in the list are all mapped."""
        inputs = {
            "messages": [
                [
                    SystemMessage(content="You are helpful."),
                    HumanMessage(content="Hi"),
                ]
            ]
        }
        data = self._parse(map_input_messages(inputs))
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["role"], "system")
        self.assertEqual(data["messages"][1]["role"], "user")

    def test_unknown_role_defaults_to_user(self) -> None:
        """Messages with an unrecognised role string default to user."""
        from langchain_core.messages import BaseMessage

        class WeirdMessage(BaseMessage):
            type: str = "xyzzy"

            def __init__(self) -> None:
                super().__init__(content="strange")

        inputs = {"messages": [[WeirdMessage()]]}
        data = self._parse(map_input_messages(inputs))
        self.assertEqual(data["messages"][0]["role"], "user")


class TestMapOutputMessages(unittest.TestCase):
    """Tests for map_output_messages."""

    def _parse(self, result: str | None) -> dict:
        self.assertIsNotNone(result)
        return json.loads(result)  # type: ignore[arg-type]

    def test_none_outputs_returns_none(self) -> None:
        """None outputs return None."""
        self.assertIsNone(map_output_messages(None))

    def test_empty_outputs_returns_none(self) -> None:
        """Empty outputs dict returns None."""
        self.assertIsNone(map_output_messages({}))

    def test_assistant_text_generation(self) -> None:
        """A plain text AI generation maps to role=assistant with a text part."""
        outputs = {
            "generations": [
                [
                    {
                        "message": AIMessage(content="Paris is the capital of France."),
                        "generation_info": {"finish_reason": "stop"},
                        "text": "Paris is the capital of France.",
                    }
                ]
            ]
        }
        data = self._parse(map_output_messages(outputs))
        self.assertEqual(data["version"], "0.1.0")
        msgs = data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "assistant")
        self.assertEqual(msgs[0]["finish_reason"], "stop")
        text_part = next(p for p in msgs[0]["parts"] if p["type"] == "text")
        self.assertEqual(text_part["content"], "Paris is the capital of France.")

    def test_tool_call_generation_args_dict(self) -> None:
        """A tool-call generation with dict args maps to a tool_call part with structured args."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calc", "id": "c1", "args": {"expr": "1+1"}, "type": "tool_use"}],
        )
        outputs = {
            "generations": [
                [
                    {
                        "message": ai_msg,
                        "text": "",
                        "generation_info": {"finish_reason": "tool_calls"},
                    }
                ]
            ]
        }
        data = self._parse(map_output_messages(outputs))
        msgs = data["messages"]
        tool_part = next(p for p in msgs[0]["parts"] if p["type"] == "tool_call")
        self.assertEqual(tool_part["name"], "calc")
        self.assertIsInstance(tool_part["arguments"], dict)
        self.assertEqual(tool_part["arguments"]["expr"], "1+1")


if __name__ == "__main__":
    unittest.main()

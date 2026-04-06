# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for message_utils conversion, normalization, and serialization helpers."""

import json
import sys
import unittest
from pathlib import Path

import pytest
from microsoft_agents_a365.observability.core.message_utils import (
    is_string_list,
    is_wrapped_messages,
    normalize_input_messages,
    normalize_output_messages,
    serialize_messages,
    to_input_messages,
    to_output_messages,
)
from microsoft_agents_a365.observability.core.models.messages import (
    A365_MESSAGE_SCHEMA_VERSION,
    BlobPart,
    ChatMessage,
    FinishReason,
    InputMessages,
    MessageRole,
    OutputMessage,
    OutputMessages,
    ReasoningPart,
    TextPart,
    ToolCallRequestPart,
)


class TestTypeGuards(unittest.TestCase):
    """Tests for is_string_list and is_wrapped_messages type guards."""

    def test_is_string_list_with_strings(self):
        self.assertTrue(is_string_list(["hello", "world"]))

    def test_is_string_list_with_empty_list(self):
        self.assertTrue(is_string_list([]))

    def test_is_string_list_with_input_messages(self):
        wrapper = InputMessages(messages=[])
        self.assertFalse(is_string_list(wrapper))

    def test_is_string_list_with_output_messages(self):
        wrapper = OutputMessages(messages=[])
        self.assertFalse(is_string_list(wrapper))

    def test_is_wrapped_messages_with_input_messages(self):
        wrapper = InputMessages(messages=[])
        self.assertTrue(is_wrapped_messages(wrapper))

    def test_is_wrapped_messages_with_output_messages(self):
        wrapper = OutputMessages(messages=[])
        self.assertTrue(is_wrapped_messages(wrapper))

    def test_is_wrapped_messages_with_string_list(self):
        self.assertFalse(is_wrapped_messages(["hello"]))

    def test_is_wrapped_messages_with_empty_list(self):
        self.assertFalse(is_wrapped_messages([]))


class TestConversion(unittest.TestCase):
    """Tests for to_input_messages and to_output_messages."""

    def test_to_input_messages_single(self):
        result = to_input_messages(["Hello"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].role, MessageRole.USER)
        self.assertEqual(len(result[0].parts), 1)
        self.assertIsInstance(result[0].parts[0], TextPart)
        self.assertEqual(result[0].parts[0].content, "Hello")

    def test_to_input_messages_multiple(self):
        result = to_input_messages(["Hello", "How are you?"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].parts[0].content, "Hello")
        self.assertEqual(result[1].parts[0].content, "How are you?")

    def test_to_input_messages_empty(self):
        result = to_input_messages([])
        self.assertEqual(result, [])

    def test_to_output_messages_single(self):
        result = to_output_messages(["Response text"])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], OutputMessage)
        self.assertEqual(result[0].role, MessageRole.ASSISTANT)
        self.assertEqual(result[0].parts[0].content, "Response text")

    def test_to_output_messages_multiple(self):
        result = to_output_messages(["First", "Second"])
        self.assertEqual(len(result), 2)
        for msg in result:
            self.assertEqual(msg.role, MessageRole.ASSISTANT)

    def test_to_output_messages_empty(self):
        result = to_output_messages([])
        self.assertEqual(result, [])


class TestNormalization(unittest.TestCase):
    """Tests for normalize_input_messages and normalize_output_messages."""

    def test_normalize_input_from_strings(self):
        result = normalize_input_messages(["Hello"])
        self.assertIsInstance(result, InputMessages)
        self.assertEqual(result.version, A365_MESSAGE_SCHEMA_VERSION)
        self.assertEqual(len(result.messages), 1)
        self.assertEqual(result.messages[0].role, MessageRole.USER)

    def test_normalize_input_from_wrapper(self):
        wrapper = InputMessages(
            messages=[
                ChatMessage(role=MessageRole.SYSTEM, parts=[TextPart(content="System prompt")])
            ]
        )
        result = normalize_input_messages(wrapper)
        self.assertIs(result, wrapper)

    def test_normalize_output_from_strings(self):
        result = normalize_output_messages(["Response"])
        self.assertIsInstance(result, OutputMessages)
        self.assertEqual(result.version, A365_MESSAGE_SCHEMA_VERSION)
        self.assertEqual(len(result.messages), 1)
        self.assertEqual(result.messages[0].role, MessageRole.ASSISTANT)

    def test_normalize_output_from_wrapper(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Answer")],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        result = normalize_output_messages(wrapper)
        self.assertIs(result, wrapper)

    def test_normalize_input_empty_list(self):
        result = normalize_input_messages([])
        self.assertIsInstance(result, InputMessages)
        self.assertEqual(result.messages, [])

    def test_normalize_output_empty_list(self):
        result = normalize_output_messages([])
        self.assertIsInstance(result, OutputMessages)
        self.assertEqual(result.messages, [])


class TestSerialization(unittest.TestCase):
    """Tests for serialize_messages."""

    def test_serialize_input_messages(self):
        wrapper = InputMessages(
            messages=[ChatMessage(role=MessageRole.USER, parts=[TextPart(content="Hello")])]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        self.assertEqual(parsed["version"], A365_MESSAGE_SCHEMA_VERSION)
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertEqual(parsed["messages"][0]["role"], "user")
        self.assertEqual(parsed["messages"][0]["parts"][0]["type"], "text")
        self.assertEqual(parsed["messages"][0]["parts"][0]["content"], "Hello")

    def test_serialize_output_messages(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Response")],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        self.assertEqual(parsed["version"], A365_MESSAGE_SCHEMA_VERSION)
        self.assertEqual(parsed["messages"][0]["role"], "assistant")
        self.assertEqual(parsed["messages"][0]["finish_reason"], "stop")

    def test_serialize_omits_none_values(self):
        wrapper = InputMessages(
            messages=[ChatMessage(role=MessageRole.USER, parts=[TextPart(content="Hi")])]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        # name is None so should not appear
        self.assertNotIn("name", parsed["messages"][0])

    def test_serialize_complex_parts(self):
        wrapper = InputMessages(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    parts=[
                        TextPart(content="Analyze this image"),
                        BlobPart(modality="image", content="base64data", mime_type="image/png"),
                    ],
                )
            ]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        parts = parsed["messages"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[1]["type"], "blob")
        self.assertEqual(parts[1]["modality"], "image")
        self.assertEqual(parts[1]["content"], "base64data")

    def test_serialize_with_tool_call_part(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ToolCallRequestPart(
                            name="search",
                            id="call_123",
                            arguments={"query": "GDPR"},
                        )
                    ],
                )
            ]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        part = parsed["messages"][0]["parts"][0]
        self.assertEqual(part["type"], "tool_call")
        self.assertEqual(part["name"], "search")
        self.assertEqual(part["id"], "call_123")
        self.assertEqual(part["arguments"], {"query": "GDPR"})

    def test_serialize_with_reasoning_part(self):
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ReasoningPart(content="Checking GDPR Article 5"),
                        TextPart(content="Based on GDPR..."),
                    ],
                    finish_reason=FinishReason.STOP.value,
                )
            ]
        )
        result = serialize_messages(wrapper)
        parsed = json.loads(result)

        parts = parsed["messages"][0]["parts"]
        self.assertEqual(parts[0]["type"], "reasoning")
        self.assertEqual(parts[0]["content"], "Checking GDPR Article 5")
        self.assertEqual(parts[1]["type"], "text")

    def test_serialize_unicode(self):
        wrapper = InputMessages(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    parts=[TextPart(content="日本語テスト 🚀")],
                )
            ]
        )
        result = serialize_messages(wrapper)
        self.assertIn("日本語テスト", result)
        self.assertIn("🚀", result)

    def test_serialize_empty_messages(self):
        wrapper = InputMessages(messages=[])
        result = serialize_messages(wrapper)
        parsed = json.loads(result)
        self.assertEqual(parsed["version"], A365_MESSAGE_SCHEMA_VERSION)
        self.assertEqual(parsed["messages"], [])


class TestVersionField(unittest.TestCase):
    """Tests for the version field on wrappers."""

    def test_input_messages_version_is_constant(self):
        wrapper = InputMessages(messages=[])
        self.assertEqual(wrapper.version, A365_MESSAGE_SCHEMA_VERSION)

    def test_output_messages_version_is_constant(self):
        wrapper = OutputMessages(messages=[])
        self.assertEqual(wrapper.version, A365_MESSAGE_SCHEMA_VERSION)

    def test_version_not_settable_via_constructor(self):
        """Version field uses init=False so it cannot be passed as a constructor arg."""
        with self.assertRaises(TypeError):
            InputMessages(messages=[], version="99.99.99")  # type: ignore[call-arg]

    def test_version_embedded_in_serialized_output(self):
        wrapper = InputMessages(messages=[])
        result = json.loads(serialize_messages(wrapper))
        self.assertEqual(result["version"], A365_MESSAGE_SCHEMA_VERSION)


if __name__ == "__main__":
    sys.exit(pytest.main([str(Path(__file__))] + sys.argv[1:]))

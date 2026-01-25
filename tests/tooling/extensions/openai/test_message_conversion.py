# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for message conversion logic in McpToolRegistrationService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from .conftest import (
    MockAssistantMessage,
    MockContentPart,
    MockResponseOutputMessage,
    MockSystemMessage,
    MockUnknownMessage,
    MockUserMessage,
)

# =============================================================================
# CONVERSION TESTS (CV-01 to CV-12)
# =============================================================================


class TestRoleConversion:
    """Tests for role extraction and mapping."""

    # CV-01
    @pytest.mark.unit
    def test_convert_user_message_to_chat_history(self, service):
        """Test that UserMessage converts with role='user'."""
        message = MockUserMessage(content="Hello from user")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "user"
        assert result.content == "Hello from user"

    # CV-02
    @pytest.mark.unit
    def test_convert_assistant_message_to_chat_history(self, service):
        """Test that AssistantMessage converts with role='assistant'."""
        message = MockAssistantMessage(content="Hello from assistant")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "assistant"
        assert result.content == "Hello from assistant"

    # CV-03
    @pytest.mark.unit
    def test_convert_system_message_to_chat_history(self, service):
        """Test that SystemMessage converts with role='system'."""
        message = MockSystemMessage(content="System instructions")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "system"
        assert result.content == "System instructions"

    # CV-10
    @pytest.mark.unit
    def test_convert_unknown_message_type_defaults_to_user(self, service):
        """Test that unknown message type defaults to 'user' role."""
        message = MockUnknownMessage(content="Unknown type content")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "user"
        assert result.content == "Unknown type content"

    @pytest.mark.unit
    def test_convert_response_output_message_to_assistant(self, service):
        """Test that ResponseOutputMessage converts with role='assistant'."""
        message = MockResponseOutputMessage(content="Response content", role="assistant")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "assistant"

    @pytest.mark.unit
    def test_extract_role_from_dict_message(self, service):
        """Test role extraction from dict-like message."""
        message = {"role": "user", "content": "Hello"}

        role = service._extract_role(message)

        assert role == "user"

    @pytest.mark.unit
    def test_extract_role_from_dict_assistant(self, service):
        """Test role extraction from dict with assistant role."""
        message = {"role": "assistant", "content": "Hi"}

        role = service._extract_role(message)

        assert role == "assistant"

    @pytest.mark.unit
    def test_extract_role_from_dict_system(self, service):
        """Test role extraction from dict with system role."""
        message = {"role": "system", "content": "Instructions"}

        role = service._extract_role(message)

        assert role == "system"


class TestContentExtraction:
    """Tests for content extraction from messages."""

    # CV-04
    @pytest.mark.unit
    def test_convert_message_with_string_content(self, service):
        """Test that string content is extracted directly."""
        message = MockUserMessage(content="Simple string content")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.content == "Simple string content"

    # CV-05
    @pytest.mark.unit
    def test_convert_message_with_list_content(self, service):
        """Test that list content is concatenated."""
        message = MockUserMessage(content=[MockContentPart("Hello, "), MockContentPart("world!")])

        result = service._convert_single_message(message)

        assert result is not None
        assert result.content == "Hello,  world!"

    # CV-11
    @pytest.mark.unit
    def test_convert_empty_content_skips_message(self, service):
        """Test that messages with empty content are skipped during conversion."""
        message = MockUserMessage(content="")

        result = service._convert_single_message(message)

        # Empty content should cause the message to be skipped
        assert result is None

    @pytest.mark.unit
    def test_extract_content_from_text_attribute(self, service):
        """Test content extraction from .text attribute as fallback."""
        message = Mock()
        message.content = None
        message.text = "Content from text attribute"

        content = service._extract_content(message)

        assert content == "Content from text attribute"

    @pytest.mark.unit
    def test_extract_content_from_dict(self, service):
        """Test content extraction from dict message."""
        message = {"role": "user", "content": "Dict content"}

        content = service._extract_content(message)

        assert content == "Dict content"

    @pytest.mark.unit
    def test_extract_content_from_dict_with_list(self, service):
        """Test content extraction from dict with list content."""
        message = {
            "role": "user",
            "content": [{"type": "text", "text": "Part 1"}, {"text": "Part 2"}],
        }

        content = service._extract_content(message)

        assert "Part 1" in content
        assert "Part 2" in content

    @pytest.mark.unit
    def test_extract_content_concatenates_string_parts(self, service):
        """Test that string parts in list are concatenated."""
        message = Mock()
        message.content = ["Hello", " ", "world"]

        content = service._extract_content(message)

        assert content == "Hello   world"


class TestIdExtraction:
    """Tests for ID extraction and generation."""

    # CV-06
    @pytest.mark.unit
    def test_convert_message_generates_uuid_when_id_missing(self, service):
        """Test that UUID is generated for messages without ID."""
        message = MockUserMessage(content="No ID message", id=None)

        result = service._convert_single_message(message)

        assert result is not None
        assert result.id is not None
        # Verify it's a valid UUID format
        try:
            uuid.UUID(result.id)
            is_valid_uuid = True
        except ValueError:
            is_valid_uuid = False
        assert is_valid_uuid

    # CV-08
    @pytest.mark.unit
    def test_convert_message_preserves_existing_id(self, service):
        """Test that existing ID is preserved."""
        message = MockUserMessage(content="Has ID", id="existing-id-123")

        result = service._convert_single_message(message)

        assert result is not None
        assert result.id == "existing-id-123"

    @pytest.mark.unit
    def test_extract_id_from_dict(self, service):
        """Test ID extraction from dict message."""
        message = {"role": "user", "content": "Hello", "id": "dict-id-456"}

        msg_id = service._extract_id(message)

        assert msg_id == "dict-id-456"

    @pytest.mark.unit
    def test_extract_id_generates_uuid_for_dict_without_id(self, service):
        """Test UUID generation for dict without ID."""
        message = {"role": "user", "content": "Hello"}

        msg_id = service._extract_id(message)

        # Should be a valid UUID
        try:
            uuid.UUID(msg_id)
            is_valid_uuid = True
        except ValueError:
            is_valid_uuid = False
        assert is_valid_uuid


class TestTimestampExtraction:
    """Tests for timestamp extraction and generation."""

    # CV-07
    @pytest.mark.unit
    def test_convert_message_uses_utc_when_timestamp_missing(self, service):
        """Test that current UTC timestamp is used when missing."""
        message = MockUserMessage(content="No timestamp", timestamp=None)
        before = datetime.now(UTC)

        result = service._convert_single_message(message)

        after = datetime.now(UTC)

        assert result is not None
        assert result.timestamp is not None
        assert before <= result.timestamp <= after

    # CV-09
    @pytest.mark.unit
    def test_convert_message_preserves_existing_timestamp(self, service):
        """Test that existing timestamp is preserved."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = MockUserMessage(content="Has timestamp", timestamp=timestamp)

        result = service._convert_single_message(message)

        assert result is not None
        assert result.timestamp == timestamp

    @pytest.mark.unit
    def test_extract_timestamp_from_created_at(self, service):
        """Test timestamp extraction from created_at attribute."""
        timestamp = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        message = Mock()
        message.timestamp = None
        message.created_at = timestamp

        result = service._extract_timestamp(message)

        assert result == timestamp

    @pytest.mark.unit
    def test_extract_timestamp_from_unix_timestamp(self, service):
        """Test timestamp extraction from Unix timestamp."""
        unix_ts = 1704067200  # 2024-01-01 00:00:00 UTC
        message = Mock()
        message.timestamp = unix_ts
        message.created_at = None

        result = service._extract_timestamp(message)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    @pytest.mark.unit
    def test_extract_timestamp_from_iso_string(self, service):
        """Test timestamp extraction from ISO format string."""
        message = Mock()
        message.timestamp = "2024-03-15T14:30:00Z"
        message.created_at = None

        result = service._extract_timestamp(message)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15


class TestBatchConversion:
    """Tests for batch message conversion."""

    # CV-12
    @pytest.mark.unit
    def test_convert_multiple_messages(self, service, sample_openai_messages):
        """Test that multiple messages are converted correctly."""
        result = service._convert_openai_messages_to_chat_history(sample_openai_messages)

        assert len(result) == len(sample_openai_messages)

        # Check alternating roles
        assert result[0].role == "user"
        assert result[1].role == "assistant"
        assert result[2].role == "user"
        assert result[3].role == "assistant"

    @pytest.mark.unit
    def test_convert_filters_out_empty_content_messages(self, service):
        """Test that messages with empty content are filtered out."""
        messages = [
            MockUserMessage(content="Valid content"),
            MockUserMessage(content=""),  # Should be filtered
            MockAssistantMessage(content="Also valid"),
        ]

        result = service._convert_openai_messages_to_chat_history(messages)

        # Only 2 messages should be converted (empty one filtered)
        assert len(result) == 2
        assert result[0].content == "Valid content"
        assert result[1].content == "Also valid"

    @pytest.mark.unit
    def test_convert_handles_mixed_message_types(self, service):
        """Test conversion of mixed message types."""
        messages = [
            MockSystemMessage(content="System prompt"),
            MockUserMessage(content="User query"),
            MockAssistantMessage(content="Assistant response"),
            MockResponseOutputMessage(content="Output message"),
        ]

        result = service._convert_openai_messages_to_chat_history(messages)

        assert len(result) == 4
        assert result[0].role == "system"
        assert result[1].role == "user"
        assert result[2].role == "assistant"
        assert result[3].role == "assistant"

    @pytest.mark.unit
    def test_convert_empty_list_returns_empty_list(self, service):
        """Test that empty input returns empty output."""
        result = service._convert_openai_messages_to_chat_history([])

        assert result == []

    @pytest.mark.unit
    def test_all_converted_messages_have_ids(self, service, sample_openai_messages):
        """Test that all converted messages have IDs."""
        result = service._convert_openai_messages_to_chat_history(sample_openai_messages)

        for msg in result:
            assert msg.id is not None
            assert len(msg.id) > 0

    @pytest.mark.unit
    def test_all_converted_messages_have_timestamps(self, service, sample_openai_messages):
        """Test that all converted messages have timestamps."""
        result = service._convert_openai_messages_to_chat_history(sample_openai_messages)

        for msg in result:
            assert msg.timestamp is not None


class TestDictMessageConversion:
    """Tests for dict-based message conversion."""

    @pytest.mark.unit
    def test_convert_dict_user_message(self, service):
        """Test conversion of dict-based user message."""
        message = {"role": "user", "content": "Hello from dict"}

        result = service._convert_single_message(message)

        assert result is not None
        assert result.role == "user"
        assert result.content == "Hello from dict"

    @pytest.mark.unit
    def test_convert_dict_with_id_and_timestamp(self, service):
        """Test conversion of dict with ID and timestamp."""
        message = {
            "role": "assistant",
            "content": "Response",
            "id": "dict-msg-id",
            "timestamp": "2024-01-15T10:30:00Z",
        }

        result = service._convert_single_message(message)

        assert result is not None
        assert result.id == "dict-msg-id"
        assert result.timestamp.year == 2024


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_message_with_only_whitespace_content_skipped(self, service):
        """Test that messages with only whitespace are skipped."""
        message = MockUserMessage(content="   ")

        result = service._convert_single_message(message)

        assert result is None

    @pytest.mark.unit
    def test_message_with_none_content_skipped(self, service):
        """Test that messages with None content are skipped."""
        message = Mock()
        message.role = "user"
        message.content = None
        message.text = None
        message.id = None
        message.timestamp = None

        result = service._convert_single_message(message)

        assert result is None

    @pytest.mark.unit
    def test_conversion_preserves_message_order(self, service):
        """Test that message order is preserved during conversion."""
        messages = [MockUserMessage(content=f"Message {i}") for i in range(10)]

        result = service._convert_openai_messages_to_chat_history(messages)

        for i, msg in enumerate(result):
            assert msg.content == f"Message {i}"

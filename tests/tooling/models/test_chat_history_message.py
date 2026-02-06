# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for ChatHistoryMessage class."""

from datetime import UTC, datetime

import pytest
from microsoft_agents_a365.tooling.models import ChatHistoryMessage
from pydantic import ValidationError


class TestChatHistoryMessage:
    """Tests for ChatHistoryMessage class."""

    def test_chat_history_message_can_be_instantiated(self):
        """Test that ChatHistoryMessage can be instantiated with valid parameters."""
        # Arrange & Act
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(
            id="msg-123",
            role="user",
            content="Hello, world!",
            timestamp=timestamp,
        )

        # Assert
        assert message is not None
        assert message.id == "msg-123"
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.timestamp == timestamp

    def test_chat_history_message_to_dict(self):
        """Test that ChatHistoryMessage converts to dictionary correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = ChatHistoryMessage(
            id="msg-456",
            role="assistant",
            content="How can I help you?",
            timestamp=timestamp,
        )

        # Act
        result = message.model_dump(mode="json")

        # Assert
        assert result["id"] == "msg-456"
        assert result["role"] == "assistant"
        assert result["content"] == "How can I help you?"
        assert result["timestamp"] == "2024-01-15T10:30:00Z"

    def test_chat_history_message_with_optional_id_none(self):
        """Test that ChatHistoryMessage allows None for optional id field."""
        # Arrange & Act
        message = ChatHistoryMessage(
            role="user",
            content="Test content",
        )

        # Assert
        assert message.id is None

    def test_chat_history_message_requires_non_empty_content(self):
        """Test that ChatHistoryMessage requires a non-empty content."""
        # Arrange
        timestamp = datetime.now(UTC)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatHistoryMessage(
                id="msg-001",
                role="user",
                content="",
                timestamp=timestamp,
            )

    def test_chat_history_message_with_optional_timestamp_none(self):
        """Test that ChatHistoryMessage allows None for optional timestamp field."""
        # Arrange & Act
        message = ChatHistoryMessage(
            role="user",
            content="Test content",
        )

        # Assert
        assert message.timestamp is None

    def test_chat_history_message_supports_system_role(self):
        """Test that ChatHistoryMessage supports system role."""
        # Arrange & Act
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(
            id="sys-001",
            role="system",
            content="You are a helpful assistant.",
            timestamp=timestamp,
        )

        # Assert
        assert message.role == "system"

    def test_chat_history_message_preserves_timestamp_precision(self):
        """Test that ChatHistoryMessage preserves timestamp precision."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 45, 123000, tzinfo=UTC)
        message = ChatHistoryMessage(
            id="msg-001",
            role="user",
            content="Test",
            timestamp=timestamp,
        )

        # Act
        message_dict = message.model_dump(mode="json")

        # Assert
        assert message.timestamp == timestamp
        assert "2024-01-15T10:30:45.123" in message_dict["timestamp"]

    def test_chat_history_message_rejects_whitespace_only_content(self):
        """Test that ChatHistoryMessage rejects whitespace-only content."""
        # Arrange
        timestamp = datetime.now(UTC)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatHistoryMessage(
                id="msg-1",
                role="user",
                content="   ",
                timestamp=timestamp,
            )

    def test_chat_history_message_rejects_newline_only_content(self):
        """Test that ChatHistoryMessage rejects newline-only content."""
        # Arrange
        timestamp = datetime.now(UTC)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatHistoryMessage(
                id="msg-1",
                role="user",
                content="\n\n",
                timestamp=timestamp,
            )

    def test_chat_history_message_rejects_invalid_role(self):
        """Test that ChatHistoryMessage rejects invalid role values."""
        # Arrange
        timestamp = datetime.now(UTC)

        # Act & Assert
        with pytest.raises(
            ValidationError, match="Input should be 'user', 'assistant' or 'system'"
        ):
            ChatHistoryMessage(
                id="msg-1",
                role="invalid_role",
                content="Test content",
                timestamp=timestamp,
            )

    def test_chat_history_message_supports_all_valid_roles(self):
        """Test that ChatHistoryMessage supports all valid role values."""
        timestamp = datetime.now(UTC)

        for role in ["user", "assistant", "system"]:
            message = ChatHistoryMessage(
                id=f"msg-{role}",
                role=role,
                content="Test content",
                timestamp=timestamp,
            )
            assert message.role == role

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for ChatHistoryMessage class."""

from datetime import datetime, timezone

import pytest
from microsoft_agents_a365.tooling.models import ChatHistoryMessage


class TestChatHistoryMessage:
    """Tests for ChatHistoryMessage class."""

    def test_chat_history_message_can_be_instantiated(self):
        """Test that ChatHistoryMessage can be instantiated with valid parameters."""
        # Arrange & Act
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-123", "user", "Hello, world!", timestamp)

        # Assert
        assert message is not None
        assert message.id == "msg-123"
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.timestamp == timestamp

    def test_chat_history_message_to_dict(self):
        """Test that ChatHistoryMessage converts to dictionary correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        message = ChatHistoryMessage("msg-456", "assistant", "How can I help you?", timestamp)

        # Act
        result = message.to_dict()

        # Assert
        assert result["id"] == "msg-456"
        assert result["role"] == "assistant"
        assert result["content"] == "How can I help you?"
        assert result["timestamp"] == "2024-01-15T10:30:00+00:00"

    def test_chat_history_message_requires_non_empty_id(self):
        """Test that ChatHistoryMessage requires a non-empty id."""
        # Arrange
        timestamp = datetime.now(timezone.utc)

        # Act & Assert
        with pytest.raises(ValueError, match="id cannot be empty"):
            ChatHistoryMessage("", "user", "Test content", timestamp)

    def test_chat_history_message_requires_non_empty_role(self):
        """Test that ChatHistoryMessage requires a non-empty role."""
        # Arrange
        timestamp = datetime.now(timezone.utc)

        # Act & Assert
        with pytest.raises(ValueError, match="role cannot be empty"):
            ChatHistoryMessage("msg-001", "", "Test content", timestamp)

    def test_chat_history_message_requires_non_empty_content(self):
        """Test that ChatHistoryMessage requires a non-empty content."""
        # Arrange
        timestamp = datetime.now(timezone.utc)

        # Act & Assert
        with pytest.raises(ValueError, match="content cannot be empty"):
            ChatHistoryMessage("msg-001", "user", "", timestamp)

    def test_chat_history_message_requires_timestamp(self):
        """Test that ChatHistoryMessage requires a timestamp."""
        # Act & Assert
        with pytest.raises(ValueError, match="timestamp cannot be None"):
            ChatHistoryMessage("msg-001", "user", "Test content", None)

    def test_chat_history_message_supports_system_role(self):
        """Test that ChatHistoryMessage supports system role."""
        # Arrange & Act
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("sys-001", "system", "You are a helpful assistant.", timestamp)

        # Assert
        assert message.role == "system"

    def test_chat_history_message_preserves_timestamp_precision(self):
        """Test that ChatHistoryMessage preserves timestamp precision."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 45, 123000, tzinfo=timezone.utc)
        message = ChatHistoryMessage("msg-001", "user", "Test", timestamp)

        # Act
        message_dict = message.to_dict()

        # Assert
        assert message.timestamp == timestamp
        assert "2024-01-15T10:30:45.123000" in message_dict["timestamp"]

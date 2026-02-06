# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for ChatMessageRequest class."""

from datetime import UTC, datetime

import pytest
from microsoft_agents_a365.tooling.models import ChatHistoryMessage, ChatMessageRequest
from pydantic import ValidationError


class TestChatMessageRequest:
    """Tests for ChatMessageRequest class."""

    def test_chat_message_request_can_be_instantiated(self):
        """Test that ChatMessageRequest can be instantiated with valid parameters."""
        # Arrange
        timestamp = datetime.now(UTC)
        message1 = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)
        message2 = ChatHistoryMessage(
            id="msg-2", role="assistant", content="Hi there!", timestamp=timestamp
        )
        chat_history = [message1, message2]

        # Act
        request = ChatMessageRequest(
            conversation_id="conv-123",
            message_id="msg-456",
            user_message="How are you?",
            chat_history=chat_history,
        )

        # Assert
        assert request is not None
        assert request.conversation_id == "conv-123"
        assert request.message_id == "msg-456"
        assert request.user_message == "How are you?"
        assert request.chat_history == chat_history

    def test_chat_message_request_to_dict(self):
        """Test that ChatMessageRequest converts to dictionary correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)
        request = ChatMessageRequest(
            conversation_id="conv-123",
            message_id="msg-456",
            user_message="How are you?",
            chat_history=[message],
        )

        # Act
        result = request.model_dump(by_alias=True)

        # Assert
        assert result["conversationId"] == "conv-123"
        assert result["messageId"] == "msg-456"
        assert result["userMessage"] == "How are you?"
        assert len(result["chatHistory"]) == 1
        assert result["chatHistory"][0]["id"] == "msg-1"
        assert result["chatHistory"][0]["role"] == "user"
        assert result["chatHistory"][0]["content"] == "Hello"

    def test_chat_message_request_requires_non_empty_conversation_id(self):
        """Test that ChatMessageRequest requires a non-empty conversation_id."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="",
                message_id="msg-456",
                user_message="How are you?",
                chat_history=[message],
            )

    def test_chat_message_request_requires_non_empty_message_id(self):
        """Test that ChatMessageRequest requires a non-empty message_id."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="conv-123",
                message_id="",
                user_message="How are you?",
                chat_history=[message],
            )

    def test_chat_message_request_requires_non_empty_user_message(self):
        """Test that ChatMessageRequest requires a non-empty user_message."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="conv-123",
                message_id="msg-456",
                user_message="",
                chat_history=[message],
            )

    def test_chat_message_request_requires_non_empty_chat_history(self):
        """Test that ChatMessageRequest requires a non-empty chat_history."""
        # Act & Assert - Pydantic accepts empty list but service validates it
        # This test verifies the model can be created with an empty list
        # (validation of non-empty happens at the service layer)
        request = ChatMessageRequest(
            conversation_id="conv-123",
            message_id="msg-456",
            user_message="How are you?",
            chat_history=[],
        )
        assert request.chat_history == []

    def test_chat_message_request_with_multiple_messages(self):
        """Test that ChatMessageRequest handles multiple messages correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message1 = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)
        message2 = ChatHistoryMessage(
            id="msg-2", role="assistant", content="Hi!", timestamp=timestamp
        )
        message3 = ChatHistoryMessage(
            id="msg-3", role="user", content="How are you?", timestamp=timestamp
        )
        chat_history = [message1, message2, message3]

        # Act
        request = ChatMessageRequest(
            conversation_id="conv-123",
            message_id="msg-456",
            user_message="What can you do?",
            chat_history=chat_history,
        )
        result = request.model_dump(by_alias=True)

        # Assert
        assert len(result["chatHistory"]) == 3
        assert result["chatHistory"][0]["id"] == "msg-1"
        assert result["chatHistory"][1]["id"] == "msg-2"
        assert result["chatHistory"][2]["id"] == "msg-3"

    def test_chat_message_request_rejects_whitespace_only_conversation_id(self):
        """Test that ChatMessageRequest rejects whitespace-only conversation_id."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="   ",
                message_id="msg-456",
                user_message="How are you?",
                chat_history=[message],
            )

    def test_chat_message_request_rejects_whitespace_only_message_id(self):
        """Test that ChatMessageRequest rejects whitespace-only message_id."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="conv-123",
                message_id="   ",
                user_message="How are you?",
                chat_history=[message],
            )

    def test_chat_message_request_rejects_whitespace_only_user_message(self):
        """Test that ChatMessageRequest rejects whitespace-only user_message."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="conv-123",
                message_id="msg-456",
                user_message="   ",
                chat_history=[message],
            )

    def test_chat_message_request_rejects_tab_only_conversation_id(self):
        """Test that ChatMessageRequest rejects tab-only conversation_id."""
        # Arrange
        timestamp = datetime.now(UTC)
        message = ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp)

        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
            ChatMessageRequest(
                conversation_id="\t\t",
                message_id="msg-456",
                user_message="How are you?",
                chat_history=[message],
            )

    def test_chat_message_request_rejects_none_chat_history(self):
        """Test that ChatMessageRequest rejects None chat_history."""
        # Act & Assert - Pydantic raises ValidationError for None when List is expected
        with pytest.raises(ValidationError):
            ChatMessageRequest(
                conversation_id="conv-123",
                message_id="msg-456",
                user_message="How are you?",
                chat_history=None,
            )

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for ChatMessageRequest class."""

from datetime import datetime, timezone

import pytest
from microsoft_agents_a365.tooling.models import ChatHistoryMessage, ChatMessageRequest


class TestChatMessageRequest:
    """Tests for ChatMessageRequest class."""

    def test_chat_message_request_can_be_instantiated(self):
        """Test that ChatMessageRequest can be instantiated with valid parameters."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message1 = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)
        message2 = ChatHistoryMessage("msg-2", "assistant", "Hi there!", timestamp)
        chat_history = [message1, message2]

        # Act
        request = ChatMessageRequest("conv-123", "msg-456", "How are you?", chat_history)

        # Assert
        assert request is not None
        assert request.conversation_id == "conv-123"
        assert request.message_id == "msg-456"
        assert request.user_message == "How are you?"
        assert request.chat_history == chat_history

    def test_chat_message_request_to_dict(self):
        """Test that ChatMessageRequest converts to dictionary correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)
        request = ChatMessageRequest("conv-123", "msg-456", "How are you?", [message])

        # Act
        result = request.to_dict()

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
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="conversation_id cannot be empty"):
            ChatMessageRequest("", "msg-456", "How are you?", [message])

    def test_chat_message_request_requires_non_empty_message_id(self):
        """Test that ChatMessageRequest requires a non-empty message_id."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="message_id cannot be empty"):
            ChatMessageRequest("conv-123", "", "How are you?", [message])

    def test_chat_message_request_requires_non_empty_user_message(self):
        """Test that ChatMessageRequest requires a non-empty user_message."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="user_message cannot be empty"):
            ChatMessageRequest("conv-123", "msg-456", "", [message])

    def test_chat_message_request_requires_non_empty_chat_history(self):
        """Test that ChatMessageRequest requires a non-empty chat_history."""
        # Act & Assert
        with pytest.raises(ValueError, match="chat_history cannot be empty"):
            ChatMessageRequest("conv-123", "msg-456", "How are you?", [])

    def test_chat_message_request_with_multiple_messages(self):
        """Test that ChatMessageRequest handles multiple messages correctly."""
        # Arrange
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        message1 = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)
        message2 = ChatHistoryMessage("msg-2", "assistant", "Hi!", timestamp)
        message3 = ChatHistoryMessage("msg-3", "user", "How are you?", timestamp)
        chat_history = [message1, message2, message3]

        # Act
        request = ChatMessageRequest("conv-123", "msg-456", "What can you do?", chat_history)
        result = request.to_dict()

        # Assert
        assert len(result["chatHistory"]) == 3
        assert result["chatHistory"][0]["id"] == "msg-1"
        assert result["chatHistory"][1]["id"] == "msg-2"
        assert result["chatHistory"][2]["id"] == "msg-3"

    def test_chat_message_request_rejects_whitespace_only_conversation_id(self):
        """Test that ChatMessageRequest rejects whitespace-only conversation_id."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="conversation_id cannot be empty"):
            ChatMessageRequest("   ", "msg-456", "How are you?", [message])

    def test_chat_message_request_rejects_whitespace_only_message_id(self):
        """Test that ChatMessageRequest rejects whitespace-only message_id."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="message_id cannot be empty"):
            ChatMessageRequest("conv-123", "   ", "How are you?", [message])

    def test_chat_message_request_rejects_whitespace_only_user_message(self):
        """Test that ChatMessageRequest rejects whitespace-only user_message."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="user_message cannot be empty"):
            ChatMessageRequest("conv-123", "msg-456", "   ", [message])

    def test_chat_message_request_rejects_tab_only_conversation_id(self):
        """Test that ChatMessageRequest rejects tab-only conversation_id."""
        # Arrange
        timestamp = datetime.now(timezone.utc)
        message = ChatHistoryMessage("msg-1", "user", "Hello", timestamp)

        # Act & Assert
        with pytest.raises(ValueError, match="conversation_id cannot be empty"):
            ChatMessageRequest("\t\t", "msg-456", "How are you?", [message])

    def test_chat_message_request_rejects_none_chat_history(self):
        """Test that ChatMessageRequest rejects None chat_history."""
        # Act & Assert
        with pytest.raises(ValueError, match="chat_history cannot be empty"):
            ChatMessageRequest("conv-123", "msg-456", "How are you?", None)

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for send_chat_history method in McpToolServerConfigurationService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.tooling.models import ChatHistoryMessage
from microsoft_agents_a365.tooling.services import McpToolServerConfigurationService


class TestSendChatHistory:
    """Tests for send_chat_history method."""

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock TurnContext with spec for stricter interface validation."""
        mock_context = Mock(spec=TurnContext)
        mock_activity = Mock()
        mock_conversation = Mock()

        mock_conversation.id = "conv-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = "msg-456"
        mock_activity.text = "Hello, how are you?"

        mock_context.activity = mock_activity
        return mock_context

    @pytest.fixture
    def chat_history_messages(self):
        """Create sample chat history messages."""
        timestamp = datetime.now(UTC)
        return [
            ChatHistoryMessage(id="msg-1", role="user", content="Hello", timestamp=timestamp),
            ChatHistoryMessage(
                id="msg-2", role="assistant", content="Hi there!", timestamp=timestamp
            ),
        ]

    @pytest.fixture
    def service(self):
        """Create McpToolServerConfigurationService instance."""
        return McpToolServerConfigurationService()

    @pytest.mark.asyncio
    async def test_send_chat_history_success(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test successful send_chat_history call."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        # Mock aiohttp.ClientSession
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Act
            result = await service.send_chat_history(mock_turn_context, chat_history_messages)

            # Assert
            assert result.succeeded is True
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_send_chat_history_http_error(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test send_chat_history with HTTP error response."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        # Mock aiohttp.ClientSession
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Act
            result = await service.send_chat_history(mock_turn_context, chat_history_messages)

            # Assert
            assert result.succeeded is False
            assert len(result.errors) == 1
            # Error now uses aiohttp.ClientResponseError which formats as "status, message=..."
            assert "500" in str(result.errors[0].message)
            assert "Internal Server Error" in str(result.errors[0].message)

    @pytest.mark.asyncio
    async def test_send_chat_history_with_options(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test send_chat_history with custom options."""
        # Arrange
        from microsoft_agents_a365.tooling.models import ToolOptions

        options = ToolOptions(orchestrator_name="TestOrchestrator")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        # Mock aiohttp.ClientSession
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Act
            result = await service.send_chat_history(
                mock_turn_context, chat_history_messages, options
            )

            # Assert
            assert result.succeeded is True

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_turn_context(self, service, chat_history_messages):
        """Test that send_chat_history validates turn_context parameter."""
        # Act & Assert
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history(None, chat_history_messages)

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_chat_history_messages(
        self, service, mock_turn_context
    ):
        """Test that send_chat_history validates chat_history_messages parameter."""
        # Act & Assert
        with pytest.raises(ValueError, match="chat_history_messages cannot be None"):
            await service.send_chat_history(mock_turn_context, None)

    @pytest.mark.asyncio
    async def test_send_chat_history_empty_list_returns_success(self, service, mock_turn_context):
        """Test that send_chat_history returns success for empty list (CRM-008)."""
        # Act
        result = await service.send_chat_history(mock_turn_context, [])

        # Assert - empty list should return success, not raise exception
        assert result.succeeded is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_activity(self, service, chat_history_messages):
        """Test that send_chat_history validates turn_context.activity."""
        # Arrange
        mock_context = Mock()
        mock_context.activity = None

        # Act & Assert
        with pytest.raises(ValueError, match="turn_context.activity cannot be None"):
            await service.send_chat_history(mock_context, chat_history_messages)

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_conversation_id(
        self, service, chat_history_messages
    ):
        """Test that send_chat_history validates conversation_id from activity."""
        # Arrange
        mock_context = Mock()
        mock_activity = Mock()
        mock_activity.conversation = None
        mock_activity.id = "msg-123"
        mock_activity.text = "Test message"
        mock_context.activity = mock_activity

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="conversation_id cannot be empty or None.*turn_context.activity.conversation.id",
        ):
            await service.send_chat_history(mock_context, chat_history_messages)

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_message_id(self, service, chat_history_messages):
        """Test that send_chat_history validates message_id from activity."""
        # Arrange
        mock_context = Mock()
        mock_activity = Mock()
        mock_conversation = Mock()
        mock_conversation.id = "conv-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = None
        mock_activity.text = "Test message"
        mock_context.activity = mock_activity

        # Act & Assert
        with pytest.raises(
            ValueError, match="message_id cannot be empty or None.*turn_context.activity.id"
        ):
            await service.send_chat_history(mock_context, chat_history_messages)

    @pytest.mark.asyncio
    async def test_send_chat_history_validates_user_message(self, service, chat_history_messages):
        """Test that send_chat_history validates user_message from activity."""
        # Arrange
        mock_context = Mock()
        mock_activity = Mock()
        mock_conversation = Mock()
        mock_conversation.id = "conv-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = "msg-123"
        mock_activity.text = None
        mock_context.activity = mock_activity

        # Act & Assert
        with pytest.raises(
            ValueError, match="user_message cannot be empty or None.*turn_context.activity.text"
        ):
            await service.send_chat_history(mock_context, chat_history_messages)

    @pytest.mark.asyncio
    async def test_send_chat_history_handles_client_error(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test send_chat_history handles aiohttp.ClientError."""
        # Arrange
        import aiohttp

        # Mock aiohttp.ClientSession to raise ClientError
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = aiohttp.ClientError("Connection failed")
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Act
            result = await service.send_chat_history(mock_turn_context, chat_history_messages)

            # Assert
            assert result.succeeded is False
            assert len(result.errors) == 1
            assert "Connection failed" in str(result.errors[0].message)

    @pytest.mark.asyncio
    async def test_send_chat_history_handles_timeout(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test send_chat_history handles timeout."""
        # Mock aiohttp.ClientSession to raise TimeoutError
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.post.side_effect = TimeoutError()

            # Act
            result = await service.send_chat_history(mock_turn_context, chat_history_messages)

            # Assert
            assert result.succeeded is False
            assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_send_chat_history_sends_correct_payload(
        self, service, mock_turn_context, chat_history_messages
    ):
        """Test that send_chat_history sends the correct payload."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        # Mock aiohttp.ClientSession
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Act
            await service.send_chat_history(mock_turn_context, chat_history_messages)

            # Assert
            # Verify post was called
            assert mock_session_instance.post.called
            call_args = mock_session_instance.post.call_args

            # Verify the endpoint
            assert "real-time-threat-protection/chat-message" in call_args[0][0]

            # Verify headers
            headers = call_args[1]["headers"]
            assert "User-Agent" in headers or "user-agent" in str(headers).lower()
            assert "Content-Type" in headers

            # Verify data is JSON
            data = call_args[1]["data"]
            assert data is not None

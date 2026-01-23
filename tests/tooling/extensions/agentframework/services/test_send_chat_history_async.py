# Copyright (c) Microsoft. All rights reserved.

"""Unit tests for send_chat_history_async methods in McpToolRegistrationService."""

# Direct import from service file to work around namespace package resolution issues
# with editable installs in the uv workspace
import importlib.util
import sys
from pathlib import Path

_service_path = (
    Path(__file__).parent.parent.parent.parent.parent.parent
    / "libraries"
    / "microsoft-agents-a365-tooling-extensions-agentframework"
    / "microsoft_agents_a365"
    / "tooling"
    / "extensions"
    / "agentframework"
    / "services"
    / "mcp_tool_registration_service.py"
)
_spec = importlib.util.spec_from_file_location("mcp_tool_registration_service", _service_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["mcp_tool_registration_service"] = _module
_spec.loader.exec_module(_module)
McpToolRegistrationService = _module.McpToolRegistrationService

from datetime import UTC, datetime  # noqa: E402
from unittest.mock import AsyncMock, Mock, patch  # noqa: E402

import pytest  # noqa: E402
from microsoft_agents.hosting.core import TurnContext  # noqa: E402
from microsoft_agents_a365.runtime import OperationError, OperationResult  # noqa: E402
from microsoft_agents_a365.tooling.models import ToolOptions  # noqa: E402


class TestSendChatHistoryAsync:
    """Tests for send_chat_history_messages_async and send_chat_history_async methods."""

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock TurnContext with valid activity data."""
        mock_context = Mock(spec=TurnContext)
        mock_activity = Mock()
        mock_conversation = Mock()

        mock_conversation.id = "conv-test-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = "msg-test-456"
        mock_activity.text = "Test user message"

        mock_context.activity = mock_activity
        return mock_context

    @pytest.fixture
    def mock_role(self):
        """Create a mock Role object with .value property."""
        role = Mock()
        role.value = "user"
        return role

    @pytest.fixture
    def mock_assistant_role(self):
        """Create a mock Role object for assistant."""
        role = Mock()
        role.value = "assistant"
        return role

    @pytest.fixture
    def sample_chat_messages(self, mock_role, mock_assistant_role):
        """Create sample Agent Framework ChatMessage-like objects."""
        msg1 = Mock()
        msg1.message_id = "msg-1"
        msg1.role = mock_role
        msg1.text = "Hello"

        msg2 = Mock()
        msg2.message_id = "msg-2"
        msg2.role = mock_assistant_role
        msg2.text = "Hi there!"

        return [msg1, msg2]

    @pytest.fixture
    def mock_chat_message_store(self, sample_chat_messages):
        """Create a mock ChatMessageStoreProtocol."""
        store = AsyncMock()
        store.list_messages = AsyncMock(return_value=sample_chat_messages)
        return store

    @pytest.fixture
    def service(self):
        """Create McpToolRegistrationService instance with mocked core service."""
        svc = McpToolRegistrationService()
        svc._mcp_server_configuration_service = Mock()
        svc._mcp_server_configuration_service.send_chat_history = AsyncMock(
            return_value=OperationResult.success()
        )
        return svc

    # ==================== Validation Tests (8 tests) ====================

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_validates_messages_none(
        self, service, mock_turn_context
    ):
        """Test that send_chat_history_messages_async raises ValueError for None messages."""
        with pytest.raises(ValueError, match="chat_messages cannot be None"):
            await service.send_chat_history_messages_async(None, mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_validates_turn_context_none(
        self, service, sample_chat_messages
    ):
        """Test that send_chat_history_messages_async raises ValueError for None turn_context."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history_messages_async(sample_chat_messages, None)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_async_validates_store_none(self, service, mock_turn_context):
        """Test that send_chat_history_async raises ValueError for None store."""
        with pytest.raises(ValueError, match="chat_message_store cannot be None"):
            await service.send_chat_history_async(None, mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_async_validates_turn_context_none(
        self, service, mock_chat_message_store
    ):
        """Test that send_chat_history_async raises ValueError for None turn_context."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history_async(mock_chat_message_store, None)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_empty_messages_returns_success(
        self, service, mock_turn_context
    ):
        """Test that empty message list returns success with warning log."""
        # Act
        result = await service.send_chat_history_messages_async([], mock_turn_context)

        # Assert
        assert result.succeeded is True
        # Core service should not be called for empty messages
        service._mcp_server_configuration_service.send_chat_history.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_generates_uuid_for_missing_id(
        self, service, mock_turn_context, mock_role
    ):
        """Test that UUID is generated when message_id is None."""
        # Arrange
        msg = Mock()
        msg.message_id = None  # No message ID
        msg.role = mock_role
        msg.text = "Hello"

        # Act
        await service.send_chat_history_messages_async([msg], mock_turn_context)

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        assert len(history_messages) == 1
        # Verify a UUID was generated (not None and has UUID format)
        assert history_messages[0].id is not None
        assert len(history_messages[0].id) == 36  # UUID format: 8-4-4-4-12

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_generates_timestamp(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test that current UTC timestamp is generated for messages."""
        # Act
        before_time = datetime.now(UTC)
        await service.send_chat_history_messages_async(sample_chat_messages, mock_turn_context)
        after_time = datetime.now(UTC)

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        for msg in history_messages:
            assert msg.timestamp is not None
            assert before_time <= msg.timestamp <= after_time

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_handles_missing_text(
        self, service, mock_turn_context, mock_role
    ):
        """Test that messages with None text are skipped (empty content not allowed)."""
        # Arrange
        msg_with_text = Mock()
        msg_with_text.message_id = "msg-1"
        msg_with_text.role = mock_role
        msg_with_text.text = "Hello"

        msg_without_text = Mock()
        msg_without_text.message_id = "msg-2"
        msg_without_text.role = mock_role
        msg_without_text.text = None  # No text

        # Act
        await service.send_chat_history_messages_async(
            [msg_with_text, msg_without_text], mock_turn_context
        )

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        # Only the message with text should be included
        assert len(history_messages) == 1
        assert history_messages[0].content == "Hello"

    # ==================== Success and Delegation Tests (5 tests) ====================

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_success(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test successful send_chat_history_messages_async call."""
        # Act
        result = await service.send_chat_history_messages_async(
            sample_chat_messages, mock_turn_context
        )

        # Assert
        assert result.succeeded is True
        assert len(result.errors) == 0
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_async_with_store_success(
        self, service, mock_turn_context, mock_chat_message_store
    ):
        """Test successful send_chat_history_async call with ChatMessageStore."""
        # Act
        result = await service.send_chat_history_async(mock_chat_message_store, mock_turn_context)

        # Assert
        assert result.succeeded is True
        mock_chat_message_store.list_messages.assert_called_once()
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_async_delegates_to_messages_async(
        self, service, mock_turn_context, mock_chat_message_store, sample_chat_messages
    ):
        """Test that send_chat_history_async delegates to send_chat_history_messages_async."""
        # Arrange
        with patch.object(
            service, "send_chat_history_messages_async", new_callable=AsyncMock
        ) as mock_messages_method:
            mock_messages_method.return_value = OperationResult.success()

            # Act
            result = await service.send_chat_history_async(
                mock_chat_message_store, mock_turn_context
            )

            # Assert
            assert result.succeeded is True
            mock_chat_message_store.list_messages.assert_called_once()
            mock_messages_method.assert_called_once_with(
                chat_messages=sample_chat_messages,
                turn_context=mock_turn_context,
                tool_options=None,
            )

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_with_tool_options(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test that ToolOptions are passed correctly to core service."""
        # Arrange
        options = ToolOptions(orchestrator_name="TestOrchestrator")

        # Act
        await service.send_chat_history_messages_async(
            sample_chat_messages, mock_turn_context, tool_options=options
        )

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["options"] == options

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_converts_messages_correctly(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test that ChatMessage objects are correctly converted to ChatHistoryMessage."""
        # Act
        await service.send_chat_history_messages_async(sample_chat_messages, mock_turn_context)

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        assert len(history_messages) == 2

        # Verify first message conversion
        assert history_messages[0].id == "msg-1"
        assert history_messages[0].role == "user"
        assert history_messages[0].content == "Hello"
        assert history_messages[0].timestamp is not None

        # Verify second message conversion
        assert history_messages[1].id == "msg-2"
        assert history_messages[1].role == "assistant"
        assert history_messages[1].content == "Hi there!"
        assert history_messages[1].timestamp is not None

    # ==================== Error Handling Tests (4 tests) ====================

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_handles_http_error(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test send_chat_history_messages_async handles HTTP errors from core service."""
        # Arrange
        error = OperationError(Exception("500, Internal Server Error"))
        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            return_value=OperationResult.failed(error)
        )

        # Act
        result = await service.send_chat_history_messages_async(
            sample_chat_messages, mock_turn_context
        )

        # Assert
        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "500" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_handles_timeout(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test send_chat_history_messages_async handles timeout errors."""
        # Arrange
        error = OperationError(Exception("Request timed out"))
        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            return_value=OperationResult.failed(error)
        )

        # Act
        result = await service.send_chat_history_messages_async(
            sample_chat_messages, mock_turn_context
        )

        # Assert
        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "timed out" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_handles_connection_error(
        self, service, mock_turn_context, sample_chat_messages
    ):
        """Test send_chat_history_messages_async handles connection errors."""
        # Arrange
        error = OperationError(Exception("Connection failed"))
        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            return_value=OperationResult.failed(error)
        )

        # Act
        result = await service.send_chat_history_messages_async(
            sample_chat_messages, mock_turn_context
        )

        # Assert
        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "Connection failed" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_async_role_value_conversion(
        self, service, mock_turn_context
    ):
        """Test that Role.value is used for string conversion."""
        # Arrange - Create messages with different role values
        system_role = Mock()
        system_role.value = "system"

        user_role = Mock()
        user_role.value = "user"

        assistant_role = Mock()
        assistant_role.value = "assistant"

        msg1 = Mock()
        msg1.message_id = "msg-1"
        msg1.role = system_role
        msg1.text = "System prompt"

        msg2 = Mock()
        msg2.message_id = "msg-2"
        msg2.role = user_role
        msg2.text = "User message"

        msg3 = Mock()
        msg3.message_id = "msg-3"
        msg3.role = assistant_role
        msg3.text = "Assistant response"

        # Act
        await service.send_chat_history_messages_async([msg1, msg2, msg3], mock_turn_context)

        # Assert
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        assert len(history_messages) == 3
        assert history_messages[0].role == "system"
        assert history_messages[1].role == "user"
        assert history_messages[2].role == "assistant"

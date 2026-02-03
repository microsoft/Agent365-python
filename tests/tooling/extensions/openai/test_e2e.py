# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""End-to-end tests for OpenAI send_chat_history methods with mocked HTTP.

These tests verify the complete flow from Session/messages through conversion
to the HTTP call, using mocked HTTP responses. They are marked as unit tests
because they use mocks and don't require real external services.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.tooling.models import ChatHistoryMessage

from .conftest import (
    MockAssistantMessage,
    MockSession,
    MockSystemMessage,
    MockUserMessage,
)

# =============================================================================
# END-TO-END TESTS WITH MOCKED HTTP (E2E-01 to E2E-03)
# =============================================================================


class TestEndToEndWithMockedHttp:
    """End-to-end tests with mocked HTTP dependencies.

    These tests verify the complete flow through the service but use mocked
    HTTP responses. They are marked as unit tests since no real network
    calls are made.
    """

    # E2E-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_e2e_success(self, service, mock_turn_context):
        """Test full end-to-end flow: Session -> conversion -> HTTP -> success."""
        # Create a session with realistic messages
        messages = [
            MockSystemMessage(content="You are a helpful assistant."),
            MockUserMessage(content="What is the capital of France?"),
            MockAssistantMessage(content="The capital of France is Paris."),
            MockUserMessage(content="And what about Germany?"),
            MockAssistantMessage(content="The capital of Germany is Berlin."),
        ]
        session = MockSession(items=messages)

        # Mock aiohttp.ClientSession
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session_class.return_value.__aenter__.return_value = mock_session_instance

            # Execute
            result = await service.send_chat_history(mock_turn_context, session)

            # Verify
            assert result.succeeded is True
            assert len(result.errors) == 0

            # Verify HTTP call was made
            assert mock_session_instance.post.called

    # E2E-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_e2e_server_error(self, service, mock_turn_context):
        """Test full end-to-end flow with HTTP 500 error."""
        messages = [
            MockUserMessage(content="Hello"),
            MockAssistantMessage(content="Hi there!"),
        ]
        session = MockSession(items=messages)

        # Mock aiohttp.ClientSession with 500 response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.request_info = MagicMock()
        mock_response.history = ()
        mock_response.headers = {}

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session_instance.post.return_value = mock_post
            mock_session_class.return_value.__aenter__.return_value = mock_session_instance

            # Execute
            result = await service.send_chat_history(mock_turn_context, session)

            # Verify failure
            assert result.succeeded is False
            assert len(result.errors) == 1

    # E2E-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_e2e_payload_format(self, service, mock_turn_context):
        """Test that the JSON payload has the correct structure."""
        messages = [
            MockUserMessage(content="Hello", id="user-001"),
            MockAssistantMessage(content="Hi!", id="assistant-001"),
        ]
        session = MockSession(items=messages)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        captured_payload = None

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()

            def capture_post(*args, **kwargs):
                nonlocal captured_payload
                captured_payload = kwargs.get("data")
                mock_post = AsyncMock()
                mock_post.__aenter__.return_value = mock_response
                return mock_post

            mock_session_instance.post.side_effect = capture_post
            mock_session_class.return_value.__aenter__.return_value = mock_session_instance

            # Execute
            result = await service.send_chat_history(mock_turn_context, session)

            # Verify success
            assert result.succeeded is True

            # Verify payload structure
            assert captured_payload is not None
            payload = json.loads(captured_payload)

            # Check required fields
            assert "conversationId" in payload
            assert "messageId" in payload
            assert "userMessage" in payload
            assert "chatHistory" in payload

            # Check conversation context from turn_context
            assert payload["conversationId"] == "conv-123"
            assert payload["messageId"] == "msg-456"
            assert payload["userMessage"] == "Hello, how are you?"

            # Check chat history
            chat_history = payload["chatHistory"]
            assert len(chat_history) == 2

            # Verify first message (user)
            assert chat_history[0]["role"] == "user"
            assert chat_history[0]["content"] == "Hello"
            assert chat_history[0]["id"] == "user-001"

            # Verify second message (assistant)
            assert chat_history[1]["role"] == "assistant"
            assert chat_history[1]["content"] == "Hi!"
            assert chat_history[1]["id"] == "assistant-001"


class TestConversionChainE2E:
    """End-to-end tests for the full conversion chain with mocked dependencies."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_messages_converted_to_chat_history_message_type(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that OpenAI messages are converted to ChatHistoryMessage instances."""
        captured_messages = None

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            def capture_args(*args, **kwargs):
                nonlocal captured_messages
                captured_messages = kwargs.get("chat_history_messages")
                return OperationResult.success()

            mock_send.side_effect = capture_args

            await service.send_chat_history_messages(mock_turn_context, sample_openai_messages)

            # Verify all messages are ChatHistoryMessage instances
            assert captured_messages is not None
            for msg in captured_messages:
                assert isinstance(msg, ChatHistoryMessage)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_session_extraction_and_conversion_chain(self, service, mock_turn_context):
        """Test the full chain: session.get_items() -> conversion -> send."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        messages = [
            MockUserMessage(content="Query", id="q-1", timestamp=timestamp),
            MockAssistantMessage(content="Response", id="r-1", timestamp=timestamp),
        ]
        session = MockSession(items=messages)

        captured_messages = None

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:

            def capture_args(*args, **kwargs):
                nonlocal captured_messages
                captured_messages = kwargs.get("chat_history_messages")
                return OperationResult.success()

            mock_send.side_effect = capture_args

            result = await service.send_chat_history(mock_turn_context, session)

            # Verify success
            assert result.succeeded is True

            # Verify messages were extracted and converted
            assert captured_messages is not None
            assert len(captured_messages) == 2

            # Verify IDs were preserved
            assert captured_messages[0].id == "q-1"
            assert captured_messages[1].id == "r-1"

            # Verify timestamps were preserved
            assert captured_messages[0].timestamp == timestamp
            assert captured_messages[1].timestamp == timestamp


class TestLimitParameterE2E:
    """End-to-end tests for the limit parameter with mocked dependencies."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_limit_restricts_session_items(self, service, mock_turn_context):
        """Test that limit parameter correctly restricts items from session."""
        # Create session with many messages
        messages = [MockUserMessage(content=f"Msg {i}") for i in range(100)]
        session = MockSession(items=messages)

        captured_messages = None

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:

            def capture_args(*args, **kwargs):
                nonlocal captured_messages
                captured_messages = kwargs.get("chat_history_messages")
                return OperationResult.success()

            mock_send.side_effect = capture_args

            # Send with limit
            result = await service.send_chat_history(mock_turn_context, session, limit=10)

            assert result.succeeded is True
            assert captured_messages is not None
            assert len(captured_messages) == 10

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_limit_sends_all_items(self, service, mock_turn_context):
        """Test that no limit sends all session items."""
        messages = [MockUserMessage(content=f"Msg {i}") for i in range(50)]
        session = MockSession(items=messages)

        captured_messages = None

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:

            def capture_args(*args, **kwargs):
                nonlocal captured_messages
                captured_messages = kwargs.get("chat_history_messages")
                return OperationResult.success()

            mock_send.side_effect = capture_args

            # Send without limit
            result = await service.send_chat_history(mock_turn_context, session)

            assert result.succeeded is True
            assert captured_messages is not None
            assert len(captured_messages) == 50


class TestHeadersE2E:
    """End-to-end tests for HTTP headers with mocked dependencies."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_agent_header_includes_orchestrator_name(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that User-Agent header includes orchestrator name."""
        captured_headers = None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()

            def capture_post(*args, **kwargs):
                nonlocal captured_headers
                captured_headers = kwargs.get("headers")
                mock_post = AsyncMock()
                mock_post.__aenter__.return_value = mock_response
                return mock_post

            mock_session_instance.post.side_effect = capture_post
            mock_session_class.return_value.__aenter__.return_value = mock_session_instance

            await service.send_chat_history_messages(mock_turn_context, sample_openai_messages)

            # Verify headers
            assert captured_headers is not None
            assert "User-Agent" in captured_headers
            # User agent should contain OpenAI or orchestrator info
            user_agent = captured_headers["User-Agent"]
            assert "OpenAI" in user_agent or "microsoft-agents" in user_agent.lower()

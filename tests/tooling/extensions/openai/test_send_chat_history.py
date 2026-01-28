# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for send_chat_history and send_chat_history_messages methods."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.tooling.models import ToolOptions

from .conftest import (
    MockSession,
    MockUserMessage,
)

# =============================================================================
# INPUT VALIDATION TESTS (UV-01 to UV-09)
# =============================================================================


class TestInputValidation:
    """Tests for input validation in send_chat_history methods."""

    # UV-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_turn_context_none(
        self, service, sample_openai_messages
    ):
        """Test that send_chat_history_messages raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history_messages(None, sample_openai_messages)

    # UV-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_messages_none(
        self, service, mock_turn_context
    ):
        """Test that send_chat_history_messages raises ValueError when messages is None."""
        with pytest.raises(ValueError, match="messages cannot be None"):
            await service.send_chat_history_messages(mock_turn_context, None)

    # UV-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_empty_list_calls_core_service(
        self, service, mock_turn_context
    ):
        """Test that empty message list still calls core service to register user message."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            result = await service.send_chat_history_messages(mock_turn_context, [])

            assert result.succeeded is True
            assert len(result.errors) == 0
            # Core service SHOULD be called even for empty messages to register the user message
            mock_send.assert_called_once()
            # Verify empty list was passed
            call_args = mock_send.call_args
            assert call_args.kwargs["chat_history_messages"] == []

    # UV-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_activity_none(
        self, service, mock_turn_context_no_activity, sample_openai_messages
    ):
        """Test that send_chat_history_messages validates turn_context.activity."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = ValueError("turn_context.activity cannot be None")

            with pytest.raises(ValueError, match="turn_context.activity cannot be None"):
                await service.send_chat_history_messages(
                    mock_turn_context_no_activity, sample_openai_messages
                )

    # UV-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_conversation_id(
        self, service, mock_turn_context_no_conversation_id, sample_openai_messages
    ):
        """Test that send_chat_history_messages validates conversation_id."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = ValueError("conversation_id cannot be empty or None")

            with pytest.raises(ValueError, match="conversation_id cannot be empty"):
                await service.send_chat_history_messages(
                    mock_turn_context_no_conversation_id, sample_openai_messages
                )

    # UV-06
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_message_id(
        self, service, mock_turn_context_no_message_id, sample_openai_messages
    ):
        """Test that send_chat_history_messages validates message_id."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = ValueError("message_id cannot be empty or None")

            with pytest.raises(ValueError, match="message_id cannot be empty"):
                await service.send_chat_history_messages(
                    mock_turn_context_no_message_id, sample_openai_messages
                )

    # UV-07
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_user_message(
        self, service, mock_turn_context_no_user_message, sample_openai_messages
    ):
        """Test that send_chat_history_messages validates user_message text."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = ValueError("user_message cannot be empty or None")

            with pytest.raises(ValueError, match="user_message cannot be empty"):
                await service.send_chat_history_messages(
                    mock_turn_context_no_user_message, sample_openai_messages
                )

    # UV-08
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_turn_context_none(self, service, mock_session):
        """Test that send_chat_history raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history(None, mock_session)

    # UV-09
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_session_none(self, service, mock_turn_context):
        """Test that send_chat_history raises ValueError when session is None."""
        with pytest.raises(ValueError, match="session cannot be None"):
            await service.send_chat_history(mock_turn_context, None)


# =============================================================================
# SUCCESS PATH TESTS (SP-01 to SP-07)
# =============================================================================


class TestSuccessPath:
    """Tests for successful execution paths."""

    # SP-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_success(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test successful send_chat_history_messages call."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            result = await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages
            )

            assert result.succeeded is True
            assert len(result.errors) == 0
            mock_send.assert_called_once()

    # SP-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_with_options(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test send_chat_history_messages with custom ToolOptions."""
        custom_options = ToolOptions(orchestrator_name="CustomOrchestrator")

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            result = await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages, options=custom_options
            )

            assert result.succeeded is True
            # Verify options were passed through
            call_args = mock_send.call_args
            assert call_args.kwargs["options"].orchestrator_name == "CustomOrchestrator"

    # SP-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_default_orchestrator_name(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that default orchestrator name is set to 'OpenAI'."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            await service.send_chat_history_messages(mock_turn_context, sample_openai_messages)

            # Verify default orchestrator name
            call_args = mock_send.call_args
            assert call_args.kwargs["options"].orchestrator_name == "OpenAI"

    # SP-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_delegates_to_config_service(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that send_chat_history_messages delegates to config_service."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            await service.send_chat_history_messages(mock_turn_context, sample_openai_messages)

            # Verify delegation
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            # Check turn_context was passed
            assert call_args.kwargs["turn_context"] == mock_turn_context

            # Check chat_history_messages were converted
            chat_history = call_args.kwargs["chat_history_messages"]
            assert len(chat_history) == len(sample_openai_messages)

    # SP-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_success(self, service, mock_turn_context, mock_session):
        """Test successful send_chat_history call."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            result = await service.send_chat_history(mock_turn_context, mock_session)

            assert result.succeeded is True
            mock_send.assert_called_once()

    # SP-06
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_with_limit(self, service, mock_turn_context):
        """Test send_chat_history with limit parameter."""
        # Create session with many messages
        messages = [MockUserMessage(content=f"Message {i}") for i in range(10)]
        session = MockSession(items=messages)

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            result = await service.send_chat_history(mock_turn_context, session, limit=5)

            assert result.succeeded is True

            # Verify only limited messages were sent
            call_args = mock_send.call_args
            chat_history = call_args.kwargs["chat_history_messages"]
            assert len(chat_history) == 5

    # SP-07
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_delegates_to_send_chat_history_messages(
        self, service, mock_turn_context, mock_session
    ):
        """Test that send_chat_history calls send_chat_history_messages."""
        with patch.object(
            service,
            "send_chat_history_messages",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = OperationResult.success()

            await service.send_chat_history(mock_turn_context, mock_session)

            mock_method.assert_called_once()
            call_args = mock_method.call_args
            assert call_args.kwargs["turn_context"] == mock_turn_context


# =============================================================================
# ERROR HANDLING TESTS (EH-01 to EH-05)
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    # EH-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_http_error(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test send_chat_history_messages handles HTTP errors."""

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.failed(
                MagicMock(message="HTTP 500: Internal Server Error")
            )

            result = await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages
            )

            assert result.succeeded is False

    # EH-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_timeout_error(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test send_chat_history_messages handles timeout errors."""
        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = TimeoutError("Request timed out")

            result = await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages
            )

            assert result.succeeded is False
            assert len(result.errors) == 1

    # EH-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_client_error(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test send_chat_history_messages handles network/client errors."""
        import aiohttp

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.side_effect = aiohttp.ClientError("Connection failed")

            result = await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages
            )

            assert result.succeeded is False
            assert len(result.errors) == 1

    # EH-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_conversion_error(self, service, mock_turn_context):
        """Test send_chat_history_messages handles conversion errors gracefully."""
        sample_messages = [MockUserMessage(content="Hello")]

        with patch.object(service, "_convert_openai_messages_to_chat_history") as mock_convert:
            mock_convert.side_effect = Exception("Conversion failed")

            result = await service.send_chat_history_messages(mock_turn_context, sample_messages)

            assert result.succeeded is False
            assert len(result.errors) == 1
            assert "Conversion failed" in str(result.errors[0].message)

    # EH-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_get_items_error(self, service, mock_turn_context):
        """Test send_chat_history handles session.get_items() errors."""
        # Create a mock session that raises an error
        mock_session = Mock()
        mock_session.get_items.side_effect = Exception("Session error")

        result = await service.send_chat_history(mock_turn_context, mock_session)

        assert result.succeeded is False
        assert len(result.errors) == 1


# =============================================================================
# ORCHESTRATOR NAME HANDLING TESTS
# =============================================================================


class TestOrchestratorNameHandling:
    """Tests for orchestrator name handling in options."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_options_with_none_orchestrator_name_gets_default(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that options with None orchestrator_name get default value."""
        options = ToolOptions(orchestrator_name=None)

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages, options=options
            )

            call_args = mock_send.call_args
            assert call_args.kwargs["options"].orchestrator_name == "OpenAI"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_options_preserves_custom_orchestrator_name(
        self, service, mock_turn_context, sample_openai_messages
    ):
        """Test that custom orchestrator name is preserved."""
        options = ToolOptions(orchestrator_name="MyCustomOrchestrator")

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = OperationResult.success()

            await service.send_chat_history_messages(
                mock_turn_context, sample_openai_messages, options=options
            )

            call_args = mock_send.call_args
            assert call_args.kwargs["options"].orchestrator_name == "MyCustomOrchestrator"


# =============================================================================
# THREAD SAFETY / CONCURRENT CALLS TESTS
# =============================================================================


class TestConcurrentCalls:
    """Tests for thread safety and concurrent call isolation."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_concurrent_calls_do_not_interfere(self, service, mock_turn_context):
        """Test that concurrent calls to send_chat_history_messages are isolated."""
        import asyncio

        messages1 = [MockUserMessage(content="Message set 1")]
        messages2 = [MockUserMessage(content="Message set 2")]

        captured_payloads: list[list[object]] = []

        with patch.object(
            service.config_service,
            "send_chat_history",
            new_callable=AsyncMock,
        ) as mock_send:

            async def capture_and_succeed(*args: object, **kwargs: object) -> OperationResult:
                captured_payloads.append(kwargs.get("chat_history_messages"))
                await asyncio.sleep(0.01)  # Simulate async work
                return OperationResult.success()

            mock_send.side_effect = capture_and_succeed

            # Run concurrently
            results = await asyncio.gather(
                service.send_chat_history_messages(mock_turn_context, messages1),
                service.send_chat_history_messages(mock_turn_context, messages2),
            )

            # Both should succeed independently
            assert all(r.succeeded for r in results)
            assert len(captured_payloads) == 2
            # Verify no cross-contamination
            contents = [p[0].content for p in captured_payloads]
            assert "Message set 1" in contents
            assert "Message set 2" in contents

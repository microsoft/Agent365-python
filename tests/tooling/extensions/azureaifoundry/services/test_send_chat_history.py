# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for send_chat_history methods in McpToolRegistrationService for Azure AI Foundry."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.tooling.models import ToolOptions

from .conftest import AsyncIteratorMock, MockThreadMessage

# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================


class TestInputValidation:
    """Tests for input validation in send_chat_history methods."""

    # --------------------------------------------------------------------------
    # send_chat_history_messages validation tests
    # --------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_turn_context_none(
        self, service, sample_thread_messages
    ):
        """Test that send_chat_history_messages raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history_messages(None, sample_thread_messages)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_messages_none(
        self, service, mock_turn_context
    ):
        """Test that send_chat_history_messages raises ValueError when messages is None."""
        with pytest.raises(ValueError, match="messages cannot be None"):
            await service.send_chat_history_messages(mock_turn_context, None)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_empty_list_still_calls_core_service(
        self, service, mock_turn_context
    ):
        """Test that empty message list still calls core service to register current user message."""
        result = await service.send_chat_history_messages(mock_turn_context, [])

        assert result.succeeded is True
        assert len(result.errors) == 0
        # Core service should still be called even for empty messages
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["chat_history_messages"] == []

    # --------------------------------------------------------------------------
    # send_chat_history validation tests
    # --------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_agents_client_none(self, service, mock_turn_context):
        """Test that send_chat_history raises ValueError when agents_client is None."""
        with pytest.raises(ValueError, match="agents_client cannot be None"):
            await service.send_chat_history(None, "thread-123", mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_thread_id_none(
        self, service, mock_agents_client, mock_turn_context
    ):
        """Test that send_chat_history raises ValueError when thread_id is None."""
        with pytest.raises(ValueError, match="thread_id cannot be empty"):
            await service.send_chat_history(mock_agents_client, None, mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_thread_id_empty(
        self, service, mock_agents_client, mock_turn_context
    ):
        """Test that send_chat_history raises ValueError when thread_id is empty string."""
        with pytest.raises(ValueError, match="thread_id cannot be empty"):
            await service.send_chat_history(mock_agents_client, "", mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_thread_id_whitespace(
        self, service, mock_agents_client, mock_turn_context
    ):
        """Test that send_chat_history raises ValueError when thread_id is whitespace only."""
        with pytest.raises(ValueError, match="thread_id cannot be empty"):
            await service.send_chat_history(mock_agents_client, "   ", mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_turn_context_none(self, service, mock_agents_client):
        """Test that send_chat_history raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history(mock_agents_client, "thread-123", None)


# =============================================================================
# MESSAGE CONVERSION TESTS
# =============================================================================


class TestMessageConversion:
    """Tests for message conversion logic."""

    # --------------------------------------------------------------------------
    # Content extraction tests
    # --------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extract_content_from_single_text_item(self, service):
        """Test that text content is correctly extracted from a single content item."""
        message = MockThreadMessage(
            message_id="msg-1",
            role="user",
            content_texts=["Hello, world!"],
        )

        content = service._extract_content_from_message(message)

        assert content == "Hello, world!"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extract_content_from_multiple_text_items(self, service):
        """Test that multiple content items are concatenated with spaces."""
        message = MockThreadMessage(
            message_id="msg-1",
            role="user",
            content_texts=["Part 1", "Part 2", "Part 3"],
        )

        content = service._extract_content_from_message(message)

        assert content == "Part 1 Part 2 Part 3"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extract_content_handles_empty_content_list(self, service):
        """Test that empty content list returns empty string."""
        message = MockThreadMessage(message_id="msg-1", role="user", content_texts=[])
        message.content = []

        content = service._extract_content_from_message(message)

        assert content == ""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extract_content_handles_none_content(self, service):
        """Test that None content returns empty string."""
        message = MockThreadMessage(message_id="msg-1", role="user", content_texts=[])
        message.content = None

        content = service._extract_content_from_message(message)

        assert content == ""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extract_content_handles_none_text_value(self, service):
        """Test that content item with None text.value is skipped."""
        message = MockThreadMessage(message_id="msg-1", role="user", content_texts=["Valid text"])
        # Add a content item with None text value
        from .conftest import MockMessageTextContent

        invalid_content = MockMessageTextContent("")
        invalid_content.text.value = None
        message.content.append(invalid_content)

        content = service._extract_content_from_message(message)

        assert content == "Valid text"

    # --------------------------------------------------------------------------
    # Message conversion tests
    # --------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_extracts_id_correctly(self, service):
        """Test that message ID is correctly extracted."""
        message = MockThreadMessage(message_id="unique-id-123", role="user", content_texts=["Hi"])

        result = service._convert_thread_messages_to_chat_history([message])

        assert len(result) == 1
        assert result[0].id == "unique-id-123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_extracts_role_correctly(self, service):
        """Test that message role is correctly extracted and lowercased."""
        message = MockThreadMessage(message_id="msg-1", role="user", content_texts=["Hi"])

        result = service._convert_thread_messages_to_chat_history([message])

        assert len(result) == 1
        assert result[0].role == "user"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_extracts_timestamp_correctly(self, service):
        """Test that message timestamp is correctly extracted."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = MockThreadMessage(
            message_id="msg-1", role="user", content_texts=["Hi"], created_at=timestamp
        )

        result = service._convert_thread_messages_to_chat_history([message])

        assert len(result) == 1
        assert result[0].timestamp == timestamp

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_filters_null_message(self, service):
        """Test that null messages are filtered out."""
        messages = [
            MockThreadMessage(message_id="msg-1", role="user", content_texts=["Valid"]),
            None,
            MockThreadMessage(message_id="msg-3", role="assistant", content_texts=["Also valid"]),
        ]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 2
        assert result[0].id == "msg-1"
        assert result[1].id == "msg-3"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_filters_null_id(
        self, service, mock_thread_message_none_id, mock_thread_message
    ):
        """Test that messages with null ID are filtered out."""
        messages = [mock_thread_message, mock_thread_message_none_id]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 1
        assert result[0].id == "msg-123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_filters_null_role(
        self, service, mock_thread_message_none_role, mock_thread_message
    ):
        """Test that messages with null role are filtered out."""
        messages = [mock_thread_message, mock_thread_message_none_role]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 1
        assert result[0].id == "msg-123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_filters_empty_content(
        self, service, mock_thread_message_empty_content, mock_thread_message
    ):
        """Test that messages with empty content are filtered out."""
        messages = [mock_thread_message, mock_thread_message_empty_content]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 1
        assert result[0].id == "msg-123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_filters_whitespace_only_content(
        self, service, mock_thread_message_whitespace_content, mock_thread_message
    ):
        """Test that messages with whitespace-only content are filtered out."""
        messages = [mock_thread_message, mock_thread_message_whitespace_content]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 1
        assert result[0].id == "msg-123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_all_filtered_returns_empty_list(
        self, service, mock_thread_message_none_id, mock_thread_message_empty_content
    ):
        """Test that filtering all messages returns empty list."""
        messages = [mock_thread_message_none_id, mock_thread_message_empty_content]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_convert_messages_role_enum_to_lowercase(self, service):
        """Test that different roles are properly converted to lowercase."""
        messages = [
            MockThreadMessage(message_id="msg-1", role="user", content_texts=["User msg"]),
            MockThreadMessage(
                message_id="msg-2", role="assistant", content_texts=["Assistant msg"]
            ),
            MockThreadMessage(message_id="msg-3", role="system", content_texts=["System msg"]),
        ]

        result = service._convert_thread_messages_to_chat_history(messages)

        assert len(result) == 3
        assert result[0].role == "user"
        assert result[1].role == "assistant"
        assert result[2].role == "system"


# =============================================================================
# SUCCESS PATH TESTS
# =============================================================================


class TestSuccessPath:
    """Tests for successful execution paths."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_success(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test successful send_chat_history_messages call."""
        result = await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)

        assert result.succeeded is True
        assert len(result.errors) == 0
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_with_tool_options(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that ToolOptions are passed correctly to core service."""
        options = ToolOptions(orchestrator_name="CustomOrchestrator")

        await service.send_chat_history_messages(
            mock_turn_context, sample_thread_messages, tool_options=options
        )

        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "CustomOrchestrator"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_default_orchestrator_name(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that default orchestrator name is set to 'AzureAIFoundry'."""
        await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)

        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "AzureAIFoundry"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_sets_orchestrator_if_none(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that orchestrator_name is set if options provided with None value."""
        options = ToolOptions(orchestrator_name=None)

        await service.send_chat_history_messages(
            mock_turn_context, sample_thread_messages, tool_options=options
        )

        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "AzureAIFoundry"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_delegates_to_core_service(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that send_chat_history_messages delegates to core service correctly."""
        await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)

        # Verify delegation
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args

        # Check turn_context was passed
        assert call_args.kwargs["turn_context"] == mock_turn_context

        # Check chat_history_messages were converted
        chat_history = call_args.kwargs["chat_history_messages"]
        assert len(chat_history) == len(sample_thread_messages)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_converts_messages_correctly(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that ThreadMessage objects are correctly converted to ChatHistoryMessage."""
        await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)

        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        history_messages = call_args.kwargs["chat_history_messages"]

        assert len(history_messages) == 3

        # Verify first message conversion
        assert history_messages[0].id == "msg-1"
        assert history_messages[0].role == "user"
        assert history_messages[0].content == "Hello"
        assert history_messages[0].timestamp is not None

        # Verify second message conversion
        assert history_messages[1].id == "msg-2"
        assert history_messages[1].role == "assistant"
        assert history_messages[1].content == "Hi there!"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_all_filtered_still_calls_core_service(
        self,
        service,
        mock_turn_context,
        mock_thread_message_none_id,
        mock_thread_message_empty_content,
    ):
        """Test that all messages filtered out still calls core service with empty list."""
        messages = [mock_thread_message_none_id, mock_thread_message_empty_content]

        result = await service.send_chat_history_messages(mock_turn_context, messages)

        assert result.succeeded is True
        # Core service should still be called even when all messages are filtered
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["chat_history_messages"] == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_success(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test successful send_chat_history call."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))

        result = await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

        assert result.succeeded is True
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_retrieves_from_client(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that send_chat_history retrieves messages from the client."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))

        await service.send_chat_history(mock_client, "thread-abc", mock_turn_context)

        mock_client.messages.list.assert_called_once_with(thread_id="thread-abc")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_delegates_to_send_chat_history_messages(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that send_chat_history delegates to send_chat_history_messages."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))

        with patch.object(
            service, "send_chat_history_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = OperationResult.success()

            await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

            mock_method.assert_called_once()
            call_args = mock_method.call_args
            assert call_args.kwargs["turn_context"] == mock_turn_context
            assert len(call_args.kwargs["messages"]) == len(sample_thread_messages)


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_handles_core_service_failure(
        self, service_with_failing_core, mock_turn_context, sample_thread_messages
    ):
        """Test send_chat_history_messages handles core service failure."""
        result = await service_with_failing_core.send_chat_history_messages(
            mock_turn_context, sample_thread_messages
        )

        assert result.succeeded is False
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_handles_unexpected_exception(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test send_chat_history_messages handles unexpected exceptions."""
        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        result = await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)

        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "Unexpected error" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_handles_api_error(self, service, mock_turn_context):
        """Test that send_chat_history handles Azure API errors."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(side_effect=Exception("API Error"))

        result = await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "API Error" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_handles_connection_error(self, service, mock_turn_context):
        """Test that send_chat_history handles connection errors."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(side_effect=ConnectionError("Connection failed"))

        result = await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "Connection failed" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_handles_timeout(self, service, mock_turn_context):
        """Test that send_chat_history handles timeout errors."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(side_effect=TimeoutError("Request timed out"))

        result = await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

        assert result.succeeded is False
        assert len(result.errors) == 1
        assert "timed out" in str(result.errors[0].message)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_propagates_validation_error(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that ValueError exceptions are re-raised, not wrapped."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))

        # Mock send_chat_history_messages to raise ValueError
        with patch.object(
            service, "send_chat_history_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = ValueError("turn_context cannot be None")

            with pytest.raises(ValueError, match="turn_context cannot be None"):
                await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_propagates_validation_error(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that ValueError from core service is re-raised."""
        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            side_effect=ValueError("Invalid argument")
        )

        with pytest.raises(ValueError, match="Invalid argument"):
            await service.send_chat_history_messages(mock_turn_context, sample_thread_messages)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_handles_role_without_value_attribute(self, service, mock_turn_context):
        """Test defensive handling when role doesn't have .value attribute."""
        message = Mock()
        message.id = "msg-1"
        message.role = "user"  # String, not an enum with .value
        message.content = [Mock()]
        message.content[0].text = Mock()
        message.content[0].text.value = "Hello"
        message.created_at = datetime.now(UTC)

        result = await service.send_chat_history_messages(mock_turn_context, [message])

        # Should succeed - role is handled defensively
        assert result.succeeded is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_empty_thread_still_calls_core_service(
        self, service, mock_turn_context
    ):
        """Test that empty thread still calls core service to register current user message."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock([]))

        result = await service.send_chat_history(mock_client, "thread-123", mock_turn_context)

        assert result.succeeded is True
        # Core service should still be called even for empty threads
        service._mcp_server_configuration_service.send_chat_history.assert_called_once()
        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["chat_history_messages"] == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_concurrent_calls_do_not_interfere(self, service, mock_turn_context):
        """Test that concurrent calls to send_chat_history_messages are isolated."""
        import asyncio

        messages1 = [MockThreadMessage(message_id="msg-1", role="user", content_texts=["Set 1"])]
        messages2 = [MockThreadMessage(message_id="msg-2", role="user", content_texts=["Set 2"])]

        captured_payloads = []

        async def capture_and_succeed(*args, **kwargs):
            captured_payloads.append(kwargs.get("chat_history_messages"))
            await asyncio.sleep(0.01)
            return OperationResult.success()

        service._mcp_server_configuration_service.send_chat_history = AsyncMock(
            side_effect=capture_and_succeed
        )

        results = await asyncio.gather(
            service.send_chat_history_messages(mock_turn_context, messages1),
            service.send_chat_history_messages(mock_turn_context, messages2),
        )

        assert all(r.succeeded for r in results)
        assert len(captured_payloads) == 2
        contents = [p[0].content for p in captured_payloads]
        assert "Set 1" in contents
        assert "Set 2" in contents

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_preserves_custom_orchestrator_name(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that custom orchestrator name is preserved in options."""
        options = ToolOptions(orchestrator_name="MyCustomOrchestrator")

        await service.send_chat_history_messages(
            mock_turn_context, sample_thread_messages, tool_options=options
        )

        call_args = service._mcp_server_configuration_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "MyCustomOrchestrator"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_passes_tool_options(
        self, service, mock_turn_context, sample_thread_messages
    ):
        """Test that tool_options are passed through send_chat_history."""
        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))

        options = ToolOptions(orchestrator_name="TestOrchestrator")

        with patch.object(
            service, "send_chat_history_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = OperationResult.success()

            await service.send_chat_history(
                mock_client, "thread-123", mock_turn_context, tool_options=options
            )

            call_args = mock_method.call_args
            assert call_args.kwargs["tool_options"] == options

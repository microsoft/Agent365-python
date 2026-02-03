# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for send_chat_history and send_chat_history_messages methods."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.tooling.models import ToolOptions

from .conftest import (
    MockAuthorRole,
    MockChatHistory,
    MockChatMessageContent,
)

# =============================================================================
# INPUT VALIDATION TESTS (UV-01 to UV-06)
# =============================================================================


class TestInputValidation:
    """Tests for input validation in send_chat_history methods."""

    # UV-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_turn_context_none(self, service, mock_chat_history):
        """Test that send_chat_history raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history(None, mock_chat_history)

    # UV-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_validates_chat_history_none(self, service, mock_turn_context):
        """Test that send_chat_history raises ValueError when chat_history is None."""
        with pytest.raises(ValueError, match="chat_history cannot be None"):
            await service.send_chat_history(mock_turn_context, None)

    # UV-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_turn_context_none(
        self, service, sample_sk_messages
    ):
        """Test that send_chat_history_messages raises ValueError when turn_context is None."""
        with pytest.raises(ValueError, match="turn_context cannot be None"):
            await service.send_chat_history_messages(None, sample_sk_messages)

    # UV-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_validates_messages_none(
        self, service, mock_turn_context
    ):
        """Test that send_chat_history_messages raises ValueError when messages is None."""
        with pytest.raises(ValueError, match="messages cannot be None"):
            await service.send_chat_history_messages(mock_turn_context, None)

    # UV-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_empty_list_calls_core_service(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that empty message list still calls core service to register user message."""
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history_messages(mock_turn_context, [])

        assert result.succeeded is True
        assert len(result.errors) == 0
        # Core service SHOULD be called even for empty messages
        mock_config_service.send_chat_history.assert_called_once()
        # Verify empty list was passed
        call_args = mock_config_service.send_chat_history.call_args
        assert call_args.kwargs["chat_history_messages"] == []

    # UV-06
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_whitespace_only_messages_filtered(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that messages with whitespace-only content are filtered."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content="   "),
            MockChatMessageContent(role=MockAuthorRole.USER, content="\t\n"),
            MockChatMessageContent(role=MockAuthorRole.USER, content="Valid message"),
        ]

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history_messages(mock_turn_context, messages)

        assert result.succeeded is True
        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        # Only the valid message should be included
        assert len(chat_history_messages) == 1
        assert chat_history_messages[0].content == "Valid message"


# =============================================================================
# ROLE MAPPING TESTS (RM-01)
# =============================================================================


class TestRoleMapping:
    """Tests for AuthorRole enum to string conversion."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "role,expected",
        [
            (MockAuthorRole.USER, "user"),
            (MockAuthorRole.ASSISTANT, "assistant"),
            (MockAuthorRole.SYSTEM, "system"),
            (MockAuthorRole.TOOL, "tool"),
        ],
    )
    def test_map_author_role_converts_to_lowercase(self, service, role, expected):
        """Test that AuthorRole enum values are converted to lowercase strings."""
        result = service._map_author_role(role)
        assert result == expected


# =============================================================================
# MESSAGE CONVERSION TESTS (MC-01 to MC-11)
# =============================================================================


class TestMessageConversion:
    """Tests for message conversion logic."""

    # MC-01
    @pytest.mark.unit
    def test_convert_single_sk_message_user_message(self, service):
        """Test converting a user message."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello, world!",
            metadata={"id": "msg-1"},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.role == "user"
        assert result.content == "Hello, world!"
        assert result.id == "msg-1"

    # MC-02
    @pytest.mark.unit
    def test_convert_single_sk_message_assistant_message(self, service):
        """Test converting an assistant message."""
        message = MockChatMessageContent(
            role=MockAuthorRole.ASSISTANT,
            content="Hi there!",
            metadata={"id": "msg-2"},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.role == "assistant"
        assert result.content == "Hi there!"

    # MC-03
    @pytest.mark.unit
    def test_convert_single_sk_message_system_message(self, service):
        """Test converting a system message."""
        message = MockChatMessageContent(
            role=MockAuthorRole.SYSTEM,
            content="You are helpful.",
            metadata={"id": "msg-3"},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.role == "system"
        assert result.content == "You are helpful."

    # MC-04
    @pytest.mark.unit
    def test_convert_single_sk_message_skips_null_message(self, service):
        """Test that None messages are skipped."""
        result = service._convert_single_sk_message(None, 0)
        assert result is None

    # MC-05
    @pytest.mark.unit
    def test_convert_single_sk_message_skips_empty_content(self, service):
        """Test that messages with empty content are skipped."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="",
        )

        result = service._convert_single_sk_message(message, 0)
        assert result is None

    # MC-06
    @pytest.mark.unit
    def test_convert_single_sk_message_skips_whitespace_content(self, service):
        """Test that messages with whitespace-only content are skipped."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="   ",
        )

        result = service._convert_single_sk_message(message, 0)
        assert result is None

    # MC-07
    @pytest.mark.unit
    def test_convert_single_sk_message_extracts_id_from_metadata(self, service):
        """Test that existing ID is extracted from metadata."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": "existing-id-123"},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.id == "existing-id-123"

    # MC-08
    @pytest.mark.unit
    def test_convert_single_sk_message_generates_id_when_missing(self, service):
        """Test that UUID is generated when message has no ID in metadata."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello!",
            metadata={},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.id is not None
        # Verify it's a valid UUID format
        uuid.UUID(result.id)

    # MC-09
    @pytest.mark.unit
    def test_convert_single_sk_message_extracts_timestamp_from_metadata(self, service):
        """Test that existing timestamp is extracted from metadata."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": timestamp},
        )

        result = service._convert_single_sk_message(message, 0)

        assert result is not None
        assert result.timestamp == timestamp

    # MC-10
    @pytest.mark.unit
    def test_convert_single_sk_message_generates_timestamp_when_missing(self, service):
        """Test that current UTC time is used when timestamp is missing."""
        message = MockChatMessageContent(
            role=MockAuthorRole.ASSISTANT,
            content="Hi there!",
            metadata={},
        )
        before = datetime.now(UTC)

        result = service._convert_single_sk_message(message, 0)

        after = datetime.now(UTC)
        assert result is not None
        assert before <= result.timestamp <= after

    # MC-11
    @pytest.mark.unit
    def test_convert_sk_messages_filters_invalid(self, service):
        """Test that batch conversion filters invalid messages."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content="Valid"),
            None,  # Should be filtered
            MockChatMessageContent(role=MockAuthorRole.USER, content=""),  # Should be filtered
            MockChatMessageContent(role=MockAuthorRole.ASSISTANT, content="Also valid"),
        ]

        result = service._convert_sk_messages_to_chat_history(messages)

        assert len(result) == 2
        assert result[0].content == "Valid"
        assert result[1].content == "Also valid"


# =============================================================================
# TIMESTAMP EXTRACTION TESTS
# =============================================================================


class TestTimestampExtraction:
    """Tests for timestamp extraction from various formats."""

    @pytest.mark.unit
    def test_extract_timestamp_from_unix_int(self, service):
        """Test extracting timestamp from Unix integer."""
        unix_timestamp = 1705315800  # 2024-01-15 10:30:00 UTC
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": unix_timestamp},
        )

        result = service._extract_or_generate_timestamp(message, 0)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    @pytest.mark.unit
    def test_extract_timestamp_from_unix_float(self, service):
        """Test extracting timestamp from Unix float."""
        unix_timestamp = 1705315800.123
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": unix_timestamp},
        )

        result = service._extract_or_generate_timestamp(message, 0)

        assert isinstance(result, datetime)

    @pytest.mark.unit
    def test_extract_timestamp_from_iso_string(self, service):
        """Test extracting timestamp from ISO string."""
        iso_string = "2024-01-15T10:30:00+00:00"
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": iso_string},
        )

        result = service._extract_or_generate_timestamp(message, 0)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    @pytest.mark.unit
    def test_extract_timestamp_from_iso_string_with_z(self, service):
        """Test extracting timestamp from ISO string with Z suffix."""
        iso_string = "2024-01-15T10:30:00Z"
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": iso_string},
        )

        result = service._extract_or_generate_timestamp(message, 0)

        assert result.year == 2024

    @pytest.mark.unit
    def test_extract_timestamp_from_created_at(self, service):
        """Test extracting timestamp from created_at metadata key."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"created_at": timestamp},
        )

        result = service._extract_or_generate_timestamp(message, 0)

        assert result == timestamp

    @pytest.mark.unit
    def test_extract_timestamp_logs_on_invalid_iso_string(self, service, caplog):
        """Test that invalid ISO string timestamp logs debug message and generates new timestamp."""
        import logging

        invalid_iso_string = "not-a-valid-timestamp"
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"timestamp": invalid_iso_string},
        )

        with caplog.at_level(logging.DEBUG):
            result = service._extract_or_generate_timestamp(message, 5)

        # Should generate a new timestamp (approximately now)
        assert isinstance(result, datetime)
        # Verify debug log was emitted
        assert any("Failed to parse timestamp" in record.message for record in caplog.records)
        assert any("not-a-valid-timestamp" in record.message for record in caplog.records)
        assert any("index 5" in record.message for record in caplog.records)


# =============================================================================
# SUCCESS PATH TESTS (SP-01 to SP-06)
# =============================================================================


class TestSuccessPath:
    """Tests for successful execution paths."""

    # SP-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_success(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test successful send_chat_history_messages call."""
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

        assert result.succeeded is True
        assert len(result.errors) == 0
        mock_config_service.send_chat_history.assert_called_once()

    # SP-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_with_options(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test send_chat_history_messages with custom ToolOptions."""
        custom_options = ToolOptions(orchestrator_name="CustomOrchestrator")
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history_messages(
            mock_turn_context, sample_sk_messages, options=custom_options
        )

        assert result.succeeded is True
        # Verify options were passed through
        call_args = mock_config_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "CustomOrchestrator"

    # SP-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_default_orchestrator_name(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test that default orchestrator name is set to 'SemanticKernel'."""
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

        # Verify default orchestrator name
        call_args = mock_config_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "SemanticKernel"

    # SP-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_success(
        self, service, mock_turn_context, mock_chat_history, mock_config_service
    ):
        """Test successful send_chat_history call."""
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history(mock_turn_context, mock_chat_history)

        assert result.succeeded is True
        mock_config_service.send_chat_history.assert_called_once()

    # SP-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_with_limit(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test send_chat_history with limit parameter."""
        # Create chat history with many messages
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content=f"Message {i}")
            for i in range(10)
        ]
        chat_history = MockChatHistory(messages=messages)

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        result = await service.send_chat_history(mock_turn_context, chat_history, limit=3)

        assert result.succeeded is True
        # Verify only limited messages were sent
        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        assert len(chat_history_messages) == 3
        # Verify the most recent messages were taken
        assert chat_history_messages[0].content == "Message 7"
        assert chat_history_messages[1].content == "Message 8"
        assert chat_history_messages[2].content == "Message 9"

    # SP-06
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_delegates_to_send_chat_history_messages(
        self, service, mock_turn_context, mock_chat_history
    ):
        """Test that send_chat_history calls send_chat_history_messages."""
        with patch.object(
            service,
            "send_chat_history_messages",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = OperationResult.success()

            await service.send_chat_history(mock_turn_context, mock_chat_history)

            mock_method.assert_called_once()
            call_args = mock_method.call_args
            assert call_args.kwargs["turn_context"] == mock_turn_context


# =============================================================================
# LIMIT FUNCTIONALITY TESTS (LF-01 to LF-04)
# =============================================================================


class TestLimitFunctionality:
    """Tests for message limit functionality."""

    # LF-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_limit_takes_most_recent(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that limit takes the most recent N messages."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content=f"Message {i}")
            for i in range(5)
        ]
        chat_history = MockChatHistory(messages=messages)

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history(mock_turn_context, chat_history, limit=2)

        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        # Should be the last 2 messages: Message 3 and Message 4
        assert len(chat_history_messages) == 2
        assert chat_history_messages[0].content == "Message 3"
        assert chat_history_messages[1].content == "Message 4"

    # LF-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_limit_larger_than_messages(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that all messages are sent if limit > count."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content=f"Message {i}")
            for i in range(3)
        ]
        chat_history = MockChatHistory(messages=messages)

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history(mock_turn_context, chat_history, limit=10)

        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        assert len(chat_history_messages) == 3

    # LF-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_no_limit_sends_all(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that all messages are sent without limit."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content=f"Message {i}")
            for i in range(5)
        ]
        chat_history = MockChatHistory(messages=messages)

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history(mock_turn_context, chat_history)

        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        assert len(chat_history_messages) == 5

    # LF-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_limit_zero_sends_all(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that zero limit is treated as no limit (sends all)."""
        messages = [
            MockChatMessageContent(role=MockAuthorRole.USER, content=f"Message {i}")
            for i in range(5)
        ]
        chat_history = MockChatHistory(messages=messages)

        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history(mock_turn_context, chat_history, limit=0)

        call_args = mock_config_service.send_chat_history.call_args
        chat_history_messages = call_args.kwargs["chat_history_messages"]
        # limit=0 should be treated as "no limit" per the condition `limit > 0`
        assert len(chat_history_messages) == 5


# =============================================================================
# ERROR HANDLING TESTS (EH-01 to EH-06)
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    # EH-01
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_http_error(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test send_chat_history_messages handles HTTP errors."""
        mock_config_service.send_chat_history.return_value = OperationResult.failed(
            MagicMock(message="HTTP 500: Internal Server Error")
        )

        result = await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

        assert result.succeeded is False

    # EH-02
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_timeout_error(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test send_chat_history_messages handles timeout errors."""
        mock_config_service.send_chat_history.side_effect = TimeoutError("Request timed out")

        result = await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

        assert result.succeeded is False
        assert len(result.errors) == 1

    # EH-03
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_client_error(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test send_chat_history_messages handles network/client errors."""
        import aiohttp

        mock_config_service.send_chat_history.side_effect = aiohttp.ClientError("Connection failed")

        result = await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

        assert result.succeeded is False
        assert len(result.errors) == 1

    # EH-04
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_conversion_error(self, service, mock_turn_context):
        """Test send_chat_history_messages handles conversion errors gracefully."""
        sample_messages = [MockChatMessageContent(role=MockAuthorRole.USER, content="Hello")]

        with patch.object(service, "_convert_sk_messages_to_chat_history") as mock_convert:
            mock_convert.side_effect = Exception("Conversion failed")

            result = await service.send_chat_history_messages(mock_turn_context, sample_messages)

            assert result.succeeded is False
            assert len(result.errors) == 1
            assert "Conversion failed" in str(result.errors[0].message)

    # EH-05
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_messages_core_service_value_error(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test that ValueError from core service is re-raised."""
        mock_config_service.send_chat_history.side_effect = ValueError(
            "conversation_id cannot be None"
        )

        with pytest.raises(ValueError, match="conversation_id cannot be None"):
            await service.send_chat_history_messages(mock_turn_context, sample_sk_messages)

    # EH-06
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_chat_history_extraction_error(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test send_chat_history handles errors during message extraction."""
        # Create a mock ChatHistory that raises an error when accessing messages
        broken_chat_history = Mock()
        # Use a property that raises an exception when accessed
        type(broken_chat_history).messages = property(
            fget=lambda self: (_ for _ in ()).throw(Exception("Messages access error"))
        )

        result = await service.send_chat_history(mock_turn_context, broken_chat_history)

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
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test that options with None orchestrator_name get default value."""
        options = ToolOptions(orchestrator_name=None)
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history_messages(
            mock_turn_context, sample_sk_messages, options=options
        )

        call_args = mock_config_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "SemanticKernel"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_options_preserves_custom_orchestrator_name(
        self, service, mock_turn_context, sample_sk_messages, mock_config_service
    ):
        """Test that custom orchestrator name is preserved."""
        options = ToolOptions(orchestrator_name="MyCustomOrchestrator")
        mock_config_service.send_chat_history.return_value = OperationResult.success()

        await service.send_chat_history_messages(
            mock_turn_context, sample_sk_messages, options=options
        )

        call_args = mock_config_service.send_chat_history.call_args
        assert call_args.kwargs["options"].orchestrator_name == "MyCustomOrchestrator"


# =============================================================================
# CONTENT EXTRACTION TESTS
# =============================================================================


class TestContentExtraction:
    """Tests for content extraction from messages."""

    @pytest.mark.unit
    def test_extract_content_from_string(self, service):
        """Test extracting string content."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello world",
        )

        result = service._extract_content(message)

        assert result == "Hello world"

    @pytest.mark.unit
    def test_extract_content_from_none(self, service):
        """Test extracting None content returns empty string."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content=None,
        )

        result = service._extract_content(message)

        assert result == ""

    @pytest.mark.unit
    def test_extract_content_returns_empty_for_unexpected_type(self, service, caplog):
        """Test that unexpected content types return empty string for security."""
        import logging

        # Create a message with non-string content (integer)
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content=12345,  # Integer - unexpected type
        )

        with caplog.at_level(logging.WARNING):
            result = service._extract_content(message)

        # Should return empty string to avoid potential data exposure
        assert result == ""

        # Should log warning about unexpected type
        assert any("Unexpected content type" in record.message for record in caplog.records)
        assert any("int" in record.message for record in caplog.records)

    @pytest.mark.unit
    def test_extract_content_logs_warning_for_dict_type(self, service, caplog):
        """Test that dict content type logs warning and returns empty string."""
        import logging

        # Create a message with dict content
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content={"key": "value"},  # Dict - unexpected type
        )

        with caplog.at_level(logging.WARNING):
            result = service._extract_content(message)

        # Should return empty string to avoid potential data exposure
        assert result == ""

        # Should log warning about unexpected type
        assert any("Unexpected content type" in record.message for record in caplog.records)
        assert any("dict" in record.message for record in caplog.records)


# =============================================================================
# ID EXTRACTION TESTS
# =============================================================================


class TestIdExtraction:
    """Tests for ID extraction and generation."""

    @pytest.mark.unit
    def test_extract_id_from_metadata(self, service):
        """Test extracting ID from metadata."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": "custom-id-123"},
        )

        result = service._extract_or_generate_id(message, 0)

        assert result == "custom-id-123"

    @pytest.mark.unit
    def test_extract_id_converts_to_string(self, service):
        """Test that ID is converted to string."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": 12345},
        )

        result = service._extract_or_generate_id(message, 0)

        assert result == "12345"

    @pytest.mark.unit
    def test_generate_id_when_metadata_empty(self, service):
        """Test UUID generation when metadata is empty."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={},
        )

        result = service._extract_or_generate_id(message, 0)

        # Verify it's a valid UUID
        uuid.UUID(result)

    @pytest.mark.unit
    def test_generate_id_when_id_is_none(self, service):
        """Test UUID generation when ID is None in metadata."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": None},
        )

        result = service._extract_or_generate_id(message, 0)

        # Verify it's a valid UUID
        uuid.UUID(result)

    @pytest.mark.unit
    def test_generate_id_when_id_is_empty_string(self, service):
        """Test UUID generation when ID is empty string in metadata."""
        message = MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": ""},
        )

        result = service._extract_or_generate_id(message, 0)

        # Verify it's a valid UUID
        uuid.UUID(result)


# =============================================================================
# CONCURRENT CALLS TESTS
# =============================================================================


class TestConcurrentCalls:
    """Tests for thread safety and concurrent call isolation."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_concurrent_calls_do_not_interfere(
        self, service, mock_turn_context, mock_config_service
    ):
        """Test that concurrent calls to send_chat_history_messages are isolated."""
        import asyncio

        messages1 = [MockChatMessageContent(role=MockAuthorRole.USER, content="Message set 1")]
        messages2 = [MockChatMessageContent(role=MockAuthorRole.USER, content="Message set 2")]

        captured_payloads: list[list[object]] = []

        async def capture_and_succeed(*args: object, **kwargs: object) -> OperationResult:
            captured_payloads.append(kwargs.get("chat_history_messages"))
            await asyncio.sleep(0.01)  # Simulate async work
            return OperationResult.success()

        mock_config_service.send_chat_history.side_effect = capture_and_succeed

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

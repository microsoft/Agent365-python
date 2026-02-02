# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared pytest fixtures for Semantic Kernel extension tests."""

from datetime import UTC, datetime
from enum import Enum
from typing import TypeAlias
from unittest.mock import AsyncMock, Mock

import pytest

# --------------------------------------------------------------------------
# MOCK SEMANTIC KERNEL CLASSES
# --------------------------------------------------------------------------


class MockAuthorRole(Enum):
    """Mock Semantic Kernel AuthorRole enum for testing."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

    @property
    def name(self) -> str:
        """Return the name of the role in uppercase (matching real AuthorRole behavior)."""
        # Enum.name returns the enum member name in uppercase
        return super().name


# Content can be string or None (mimics Semantic Kernel SDK)
MessageContent: TypeAlias = str | None


class MockChatMessageContent:
    """Mock Semantic Kernel ChatMessageContent for testing."""

    def __init__(
        self,
        role: MockAuthorRole = MockAuthorRole.USER,
        content: MessageContent = "Hello",
        metadata: dict | None = None,
    ):
        self.role = role
        self.content = content
        self.metadata = metadata or {}


class MockChatHistory:
    """Mock Semantic Kernel ChatHistory for testing."""

    def __init__(self, messages: list[MockChatMessageContent] | None = None):
        self._messages: list[MockChatMessageContent] = messages or []

    @property
    def messages(self) -> list[MockChatMessageContent]:
        """Return the list of messages."""
        return self._messages

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self._messages.append(MockChatMessageContent(role=MockAuthorRole.USER, content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the history."""
        self._messages.append(
            MockChatMessageContent(role=MockAuthorRole.ASSISTANT, content=content)
        )

    def add_system_message(self, content: str) -> None:
        """Add a system message to the history."""
        self._messages.append(MockChatMessageContent(role=MockAuthorRole.SYSTEM, content=content))


# Type alias for mock messages
MockMessage: TypeAlias = MockChatMessageContent


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Turn Context
# --------------------------------------------------------------------------


@pytest.fixture
def mock_turn_context():
    """Create a mock TurnContext with all required fields."""
    from microsoft_agents.hosting.core import TurnContext

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
def mock_turn_context_no_activity():
    """Create a mock TurnContext with no activity."""
    from microsoft_agents.hosting.core import TurnContext

    mock_context = Mock(spec=TurnContext)
    mock_context.activity = None
    return mock_context


@pytest.fixture
def mock_turn_context_no_conversation_id():
    """Create a mock TurnContext with no conversation ID."""
    from microsoft_agents.hosting.core import TurnContext

    mock_context = Mock(spec=TurnContext)
    mock_activity = Mock()
    mock_activity.conversation = None
    mock_activity.id = "msg-456"
    mock_activity.text = "Hello"
    mock_context.activity = mock_activity
    return mock_context


@pytest.fixture
def mock_turn_context_no_message_id():
    """Create a mock TurnContext with no message ID."""
    from microsoft_agents.hosting.core import TurnContext

    mock_context = Mock(spec=TurnContext)
    mock_activity = Mock()
    mock_conversation = Mock()
    mock_conversation.id = "conv-123"
    mock_activity.conversation = mock_conversation
    mock_activity.id = None
    mock_activity.text = "Hello"
    mock_context.activity = mock_activity
    return mock_context


@pytest.fixture
def mock_turn_context_no_user_message():
    """Create a mock TurnContext with no user message text."""
    from microsoft_agents.hosting.core import TurnContext

    mock_context = Mock(spec=TurnContext)
    mock_activity = Mock()
    mock_conversation = Mock()
    mock_conversation.id = "conv-123"
    mock_activity.conversation = mock_conversation
    mock_activity.id = "msg-456"
    mock_activity.text = None
    mock_context.activity = mock_activity
    return mock_context


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Chat Messages
# --------------------------------------------------------------------------


@pytest.fixture
def sample_user_message():
    """Create a sample user message."""
    return MockChatMessageContent(role=MockAuthorRole.USER, content="Hello, how are you?")


@pytest.fixture
def sample_assistant_message():
    """Create a sample assistant message."""
    return MockChatMessageContent(
        role=MockAuthorRole.ASSISTANT, content="I'm doing great, thank you!"
    )


@pytest.fixture
def sample_system_message():
    """Create a sample system message."""
    return MockChatMessageContent(
        role=MockAuthorRole.SYSTEM, content="You are a helpful assistant."
    )


@pytest.fixture
def sample_tool_message():
    """Create a sample tool message."""
    return MockChatMessageContent(role=MockAuthorRole.TOOL, content="Tool result here")


@pytest.fixture
def sample_sk_messages():
    """Create a list of sample Semantic Kernel messages."""
    return [
        MockChatMessageContent(role=MockAuthorRole.USER, content="Hello"),
        MockChatMessageContent(role=MockAuthorRole.ASSISTANT, content="Hi there!"),
        MockChatMessageContent(role=MockAuthorRole.USER, content="How are you?"),
        MockChatMessageContent(
            role=MockAuthorRole.ASSISTANT, content="I'm doing well, thanks for asking!"
        ),
    ]


@pytest.fixture
def sample_sk_messages_with_metadata():
    """Create sample messages with pre-existing IDs and timestamps."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    return [
        MockChatMessageContent(
            role=MockAuthorRole.USER,
            content="Hello",
            metadata={"id": "user-msg-001", "timestamp": timestamp},
        ),
        MockChatMessageContent(
            role=MockAuthorRole.ASSISTANT,
            content="Hi!",
            metadata={
                "id": "assistant-msg-001",
                "timestamp": datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
            },
        ),
    ]


@pytest.fixture
def sample_message_with_empty_content():
    """Create a message with empty content."""
    return MockChatMessageContent(role=MockAuthorRole.USER, content="")


@pytest.fixture
def sample_message_with_whitespace_content():
    """Create a message with whitespace-only content."""
    return MockChatMessageContent(role=MockAuthorRole.USER, content="   ")


@pytest.fixture
def sample_message_with_none_content():
    """Create a message with None content."""
    return MockChatMessageContent(role=MockAuthorRole.USER, content=None)


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Chat History
# --------------------------------------------------------------------------


@pytest.fixture
def mock_chat_history(sample_sk_messages):
    """Create a mock ChatHistory with sample messages."""
    return MockChatHistory(messages=sample_sk_messages)


@pytest.fixture
def mock_empty_chat_history():
    """Create a mock ChatHistory with no messages."""
    return MockChatHistory(messages=[])


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Service
# --------------------------------------------------------------------------


@pytest.fixture
def mock_config_service():
    """Create a mock McpToolServerConfigurationService."""
    from microsoft_agents_a365.runtime import OperationResult
    from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
        McpToolServerConfigurationService,
    )

    service = AsyncMock(spec=McpToolServerConfigurationService)
    service.send_chat_history = AsyncMock(return_value=OperationResult.success())
    return service


@pytest.fixture
def service(mock_config_service):
    """Create a McpToolRegistrationService instance for testing."""
    from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService

    svc = McpToolRegistrationService()
    svc._mcp_server_configuration_service = mock_config_service
    return svc

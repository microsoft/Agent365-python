# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared pytest fixtures for OpenAI extension tests."""

from datetime import UTC, datetime
from typing import TypeAlias
from unittest.mock import Mock

import pytest

# --------------------------------------------------------------------------
# TYPE DEFINITIONS
# --------------------------------------------------------------------------

# Content can be string, list of content parts, or None (mimics OpenAI SDK)
MessageContent: TypeAlias = str | list[object] | None


# --------------------------------------------------------------------------
# MOCK OPENAI MESSAGE CLASSES
# --------------------------------------------------------------------------


class MockUserMessage:
    """Mock OpenAI UserMessage for testing."""

    def __init__(
        self,
        content: MessageContent = "Hello",
        id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.role = "user"
        self.content = content
        self.id = id
        self.timestamp = timestamp


class MockAssistantMessage:
    """Mock OpenAI AssistantMessage for testing."""

    def __init__(
        self,
        content: MessageContent = "Hi there!",
        id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.role = "assistant"
        self.content = content
        self.id = id
        self.timestamp = timestamp


class MockSystemMessage:
    """Mock OpenAI SystemMessage for testing."""

    def __init__(
        self,
        content: MessageContent = "You are a helpful assistant.",
        id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.role = "system"
        self.content = content
        self.id = id
        self.timestamp = timestamp


class MockResponseOutputMessage:
    """Mock OpenAI ResponseOutputMessage for testing."""

    def __init__(
        self,
        content: MessageContent = "Response from agent",
        role: str = "assistant",
        id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.role = role
        self.content = content
        self.id = id
        self.timestamp = timestamp


class MockUnknownMessage:
    """Mock unknown message type for testing fallback behavior."""

    def __init__(self, content: MessageContent = "Unknown content"):
        self.content = content


class MockContentPart:
    """Mock content part for list-based content."""

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


# Type alias for mock messages
MockMessage: TypeAlias = (
    MockUserMessage
    | MockAssistantMessage
    | MockSystemMessage
    | MockResponseOutputMessage
    | MockUnknownMessage
)


class MockSession:
    """Mock OpenAI Session for testing."""

    def __init__(self, items: list[MockMessage] | None = None):
        self._items: list[MockMessage] = items or []

    def get_items(self, limit: int | None = None) -> list[MockMessage]:
        """Get items from the session, optionally limited."""
        if limit is not None:
            return self._items[:limit]
        return self._items


# --------------------------------------------------------------------------
# PYTEST FIXTURES
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


@pytest.fixture
def sample_user_message():
    """Create a sample user message."""
    return MockUserMessage(content="Hello, how are you?")


@pytest.fixture
def sample_assistant_message():
    """Create a sample assistant message."""
    return MockAssistantMessage(content="I'm doing great, thank you!")


@pytest.fixture
def sample_system_message():
    """Create a sample system message."""
    return MockSystemMessage(content="You are a helpful assistant.")


@pytest.fixture
def sample_openai_messages():
    """Create a list of sample OpenAI messages."""
    return [
        MockUserMessage(content="Hello"),
        MockAssistantMessage(content="Hi there!"),
        MockUserMessage(content="How are you?"),
        MockAssistantMessage(content="I'm doing well, thanks for asking!"),
    ]


@pytest.fixture
def sample_messages_with_ids():
    """Create sample messages with pre-existing IDs."""
    return [
        MockUserMessage(content="Hello", id="user-msg-001"),
        MockAssistantMessage(content="Hi!", id="assistant-msg-001"),
    ]


@pytest.fixture
def sample_messages_with_timestamps():
    """Create sample messages with pre-existing timestamps."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    return [
        MockUserMessage(content="Hello", timestamp=timestamp),
        MockAssistantMessage(
            content="Hi!",
            timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def sample_message_with_list_content():
    """Create a message with list-based content."""
    return MockUserMessage(content=[MockContentPart("Hello, "), MockContentPart("how are you?")])


@pytest.fixture
def sample_message_with_empty_content():
    """Create a message with empty content."""
    return MockUserMessage(content="")


@pytest.fixture
def sample_message_with_none_content():
    """Create a message with None content."""
    return MockUserMessage(content=None)


@pytest.fixture
def sample_unknown_message():
    """Create an unknown message type."""
    return MockUnknownMessage(content="Unknown type content")


@pytest.fixture
def mock_session(sample_openai_messages):
    """Create a mock OpenAI Session with sample messages."""
    return MockSession(items=sample_openai_messages)


@pytest.fixture
def mock_empty_session():
    """Create a mock OpenAI Session with no messages."""
    return MockSession(items=[])


@pytest.fixture
def service():
    """Create a McpToolRegistrationService instance for testing."""
    from microsoft_agents_a365.tooling.extensions.openai import McpToolRegistrationService

    return McpToolRegistrationService()

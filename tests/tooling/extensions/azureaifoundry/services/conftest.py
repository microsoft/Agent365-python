# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared pytest fixtures for Azure AI Foundry extension tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from microsoft_agents_a365.runtime import OperationResult
from microsoft_agents_a365.tooling.extensions.azureaifoundry.services import (
    McpToolRegistrationService,
)

# --------------------------------------------------------------------------
# MOCK AZURE AI FOUNDRY MESSAGE CLASSES
# --------------------------------------------------------------------------


class MockMessageTextContent:
    """Mock Azure AI Foundry MessageTextContent for testing."""

    def __init__(self, text_value: str):
        """Initialize mock MessageTextContent.

        Args:
            text_value: The text value for the content.
        """
        self.text = Mock()
        self.text.value = text_value


class MockMessageRole:
    """Mock Azure AI Foundry MessageRole enum for testing."""

    def __init__(self, value: str):
        """Initialize mock MessageRole.

        Args:
            value: The role value (user, assistant, system).
        """
        self.value = value


class MockThreadMessage:
    """Mock Azure AI Foundry ThreadMessage for testing."""

    def __init__(
        self,
        message_id: str = "msg-123",
        role: str = "user",
        content_texts: list[str] = None,
        created_at: datetime = None,
    ):
        """Initialize mock ThreadMessage.

        Args:
            message_id: The message ID.
            role: The message role (user, assistant, system).
            content_texts: List of text content strings.
            created_at: The message creation timestamp.
        """
        self.id = message_id
        self.role = MockMessageRole(role) if role is not None else None
        self.created_at = created_at or datetime.now(UTC)

        # Build content list
        if content_texts is None:
            content_texts = ["Hello, world!"]

        self.content = [MockMessageTextContent(text) for text in content_texts]


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

    mock_conversation.id = "conv-test-123"
    mock_activity.conversation = mock_conversation
    mock_activity.id = "msg-test-456"
    mock_activity.text = "Test user message"

    mock_context.activity = mock_activity
    return mock_context


@pytest.fixture
def mock_turn_context_no_activity():
    """Create a mock TurnContext with no activity."""
    from microsoft_agents.hosting.core import TurnContext

    mock_context = Mock(spec=TurnContext)
    mock_context.activity = None
    return mock_context


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Azure AI Foundry Mock Objects
# --------------------------------------------------------------------------


@pytest.fixture
def mock_role_user():
    """Create a mock MessageRole for user."""
    return MockMessageRole("user")


@pytest.fixture
def mock_role_assistant():
    """Create a mock MessageRole for assistant."""
    return MockMessageRole("assistant")


@pytest.fixture
def mock_role_system():
    """Create a mock MessageRole for system."""
    return MockMessageRole("system")


@pytest.fixture
def mock_thread_message():
    """Create a single mock ThreadMessage."""
    return MockThreadMessage(
        message_id="msg-123",
        role="user",
        content_texts=["Hello, world!"],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_thread_message_assistant():
    """Create a mock assistant ThreadMessage."""
    return MockThreadMessage(
        message_id="msg-456",
        role="assistant",
        content_texts=["Hi there!"],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_thread_messages():
    """Create a list of sample ThreadMessage objects."""
    return [
        MockThreadMessage(
            message_id="msg-1",
            role="user",
            content_texts=["Hello"],
            created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        ),
        MockThreadMessage(
            message_id="msg-2",
            role="assistant",
            content_texts=["Hi there!"],
            created_at=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
        ),
        MockThreadMessage(
            message_id="msg-3",
            role="user",
            content_texts=["How are you?"],
            created_at=datetime(2024, 1, 15, 10, 30, 10, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def mock_thread_message_multiple_content():
    """Create a mock ThreadMessage with multiple content items."""
    return MockThreadMessage(
        message_id="msg-multi",
        role="user",
        content_texts=["Part 1", "Part 2", "Part 3"],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_thread_message_empty_content():
    """Create a mock ThreadMessage with empty content."""
    msg = MockThreadMessage(
        message_id="msg-empty",
        role="user",
        content_texts=[],
    )
    msg.content = []
    return msg


@pytest.fixture
def mock_thread_message_none_id():
    """Create a mock ThreadMessage with None ID."""
    msg = MockThreadMessage(
        message_id=None,
        role="user",
        content_texts=["Some content"],
    )
    msg.id = None
    return msg


@pytest.fixture
def mock_thread_message_none_role():
    """Create a mock ThreadMessage with None role."""
    msg = MockThreadMessage(
        message_id="msg-no-role",
        role=None,
        content_texts=["Some content"],
    )
    msg.role = None
    return msg


@pytest.fixture
def mock_thread_message_whitespace_content():
    """Create a mock ThreadMessage with whitespace-only content."""
    return MockThreadMessage(
        message_id="msg-whitespace",
        role="user",
        content_texts=["   \t\n  "],
    )


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Azure Agents Client
# --------------------------------------------------------------------------


@pytest.fixture
def mock_agents_client():
    """Create a mock AgentsClient."""
    client = Mock()
    client.messages = Mock()
    # Default to returning empty list
    client.messages.list = Mock(return_value=AsyncIteratorMock([]))
    return client


@pytest.fixture
def mock_agents_client_with_messages(sample_thread_messages):
    """Create a mock AgentsClient that returns sample messages."""
    client = Mock()
    client.messages = Mock()
    client.messages.list = Mock(return_value=AsyncIteratorMock(sample_thread_messages))
    return client


class AsyncIteratorMock:
    """Mock async iterator for Azure SDK responses."""

    def __init__(self, items: list):
        """Initialize async iterator mock.

        Args:
            items: List of items to iterate over.
        """
        self.items = items
        self.index = 0

    def __aiter__(self):
        """Return self as async iterator."""
        self.index = 0
        return self

    async def __anext__(self):
        """Return next item or raise StopAsyncIteration."""
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        raise StopAsyncIteration


# --------------------------------------------------------------------------
# PYTEST FIXTURES - Service Instance
# --------------------------------------------------------------------------


@pytest.fixture
def service():
    """Create McpToolRegistrationService instance with mocked core service."""
    svc = McpToolRegistrationService()
    svc._mcp_server_configuration_service = Mock()
    svc._mcp_server_configuration_service.send_chat_history = AsyncMock(
        return_value=OperationResult.success()
    )
    return svc


@pytest.fixture
def service_with_failing_core():
    """Create McpToolRegistrationService with core service that returns failure."""
    from microsoft_agents_a365.runtime import OperationError

    svc = McpToolRegistrationService()
    svc._mcp_server_configuration_service = Mock()
    error = OperationError(Exception("Core service error"))
    svc._mcp_server_configuration_service.send_chat_history = AsyncMock(
        return_value=OperationResult.failed(error)
    )
    return svc

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Chat message request model."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .chat_history_message import ChatHistoryMessage


class ChatMessageRequest(BaseModel):
    """
    Request payload for sending chat history to MCP platform.

    This model represents the complete request body sent to the MCP platform's
    chat history endpoint for threat protection analysis. It includes the
    current conversation context and historical messages.

    The model uses field aliases to serialize to camelCase JSON format
    as required by the MCP platform API.

    Attributes:
        conversation_id: Unique identifier for the conversation.
        message_id: Unique identifier for the current message.
        user_message: The current user message being processed.
        chat_history: List of previous messages in the conversation.

    Example:
        >>> from microsoft_agents_a365.tooling.models import ChatHistoryMessage
        >>> request = ChatMessageRequest(
        ...     conversation_id="conv-123",
        ...     message_id="msg-456",
        ...     user_message="What is the weather today?",
        ...     chat_history=[
        ...         ChatHistoryMessage(role="user", content="Hello"),
        ...         ChatHistoryMessage(role="assistant", content="Hi there!"),
        ...     ]
        ... )
        >>> # Serialize to camelCase JSON
        >>> json_dict = request.model_dump(by_alias=True)
        >>> print(json_dict["conversationId"])
        'conv-123'
    """

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(
        ..., alias="conversationId", description="Unique conversation identifier"
    )
    message_id: str = Field(..., alias="messageId", description="Current message identifier")
    user_message: str = Field(..., alias="userMessage", description="The current user message")
    chat_history: List[ChatHistoryMessage] = Field(
        ..., alias="chatHistory", description="Previous messages in the conversation"
    )

    @field_validator("conversation_id", "message_id", "user_message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        """Validate that string fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v

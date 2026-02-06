# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Chat history message model."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatHistoryMessage(BaseModel):
    """
    Represents a single message in the chat history.

    This model is used to capture individual messages exchanged between
    users and the AI assistant for threat protection analysis and
    compliance monitoring.

    Attributes:
        id: Optional unique identifier for the message.
        role: The role of the message sender (user, assistant, or system).
        content: The text content of the message.
        timestamp: Optional timestamp when the message was created.

    Example:
        >>> message = ChatHistoryMessage(role="user", content="Hello, how can you help?")
        >>> print(message.role)
        'user'
        >>> print(message.content)
        'Hello, how can you help?'
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, description="Unique message identifier")
    role: Literal["user", "assistant", "system"] = Field(
        ..., description="The role of the message sender"
    )
    content: str = Field(..., description="The message content")
    timestamp: Optional[datetime] = Field(default=None, description="When the message was created")

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Validate that content is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty or whitespace")
        return v

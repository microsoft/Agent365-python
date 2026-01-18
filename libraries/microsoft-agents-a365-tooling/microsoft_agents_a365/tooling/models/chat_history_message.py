# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Chat History Message model.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class ChatHistoryMessage:
    """
    Represents a single message in the chat history.

    This class is used to send chat history to the MCP platform for real-time
    threat protection analysis.
    """

    #: The unique identifier for the chat message.
    id: str

    #: The role of the message sender (e.g., "user", "assistant", "system").
    role: str

    #: The content of the chat message.
    content: str

    #: The timestamp of when the message was sent.
    timestamp: datetime

    def __post_init__(self):
        """
        Validate the message after initialization.

        Ensures that all required fields are present and non-empty.

        Raises:
            ValueError: If id, role, or content is empty or whitespace-only,
                        or if timestamp is None.
        """
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.role or not self.role.strip():
            raise ValueError("role cannot be empty")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.timestamp is None:
            raise ValueError("timestamp cannot be None")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the message to a dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the message.
        """
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

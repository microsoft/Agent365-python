# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Chat Message Request model.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from .chat_history_message import ChatHistoryMessage


@dataclass
class ChatMessageRequest:
    """
    Represents the request payload for a real-time threat protection check on a chat message.

    This class encapsulates the information needed to send chat history to the MCP platform
    for threat analysis.
    """

    #: The unique identifier for the conversation.
    conversation_id: str

    #: The unique identifier for the message within the conversation.
    message_id: str

    #: The content of the user's message.
    user_message: str

    #: The chat history messages.
    chat_history: List[ChatHistoryMessage]

    def __post_init__(self):
        """
        Validate the request after initialization.

        Ensures that all required fields are present and non-empty.

        Raises:
            ValueError: If conversation_id, message_id, or user_message is empty
                        or whitespace-only, or if chat_history is None or empty.
        """
        if not self.conversation_id or not self.conversation_id.strip():
            raise ValueError("conversation_id cannot be empty")
        if not self.message_id or not self.message_id.strip():
            raise ValueError("message_id cannot be empty")
        if not self.user_message or not self.user_message.strip():
            raise ValueError("user_message cannot be empty")
        if self.chat_history is None or len(self.chat_history) == 0:
            raise ValueError("chat_history cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the request to a dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the request.
        """
        return {
            "conversationId": self.conversation_id,
            "messageId": self.message_id,
            "userMessage": self.user_message,
            "chatHistory": [msg.to_dict() for msg in self.chat_history],
        }

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal
from microsoft_agents.activity.entity import Entity
from .notification_types import NotificationTypes


class EmailReference(Entity):
    """Entity representing an email notification reference.

    This class encapsulates information about an email notification that an agent
    receives from Outlook, including the email ID, conversation context, and content.

    Attributes:
        type: The notification type identifier, always set to "emailNotification".
        id: The unique identifier of the email message.
        conversation_id: The identifier of the conversation thread this email belongs to.
        html_body: The HTML content of the email body.
    """

    type: Literal["emailNotification"] = NotificationTypes.EMAIL_NOTIFICATION
    id: Optional[str] = None
    conversation_id: Optional[str] = None
    html_body: Optional[str] = None

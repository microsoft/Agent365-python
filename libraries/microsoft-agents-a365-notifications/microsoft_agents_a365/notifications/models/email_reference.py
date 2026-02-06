# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal
from microsoft_agents.activity.entity import Entity
from .notification_types import NotificationTypes


class EmailReference(Entity):
    type: Literal["emailNotification"] = NotificationTypes.EMAIL_NOTIFICATION
    id: Optional[str] = None
    conversation_id: Optional[str] = None
    html_body: Optional[str] = None

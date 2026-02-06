# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Models and data classes for agent notifications.

This module contains the data models and enums used to represent notifications
from Microsoft 365 applications, including email references, document comments,
and lifecycle events.
"""

from .agent_lifecycle_event import AgentLifecycleEvent
from .agent_notification_activity import AgentNotificationActivity
from .agent_subchannel import AgentSubChannel
from .email_reference import EmailReference
from .email_response import EmailResponse
from .notification_types import NotificationTypes
from .wpx_comment import WpxComment

__all__ = [
    "AgentNotificationActivity",
    "EmailReference",
    "WpxComment",
    "EmailResponse",
    "NotificationTypes",
    "AgentSubChannel",
    "AgentLifecycleEvent",
]

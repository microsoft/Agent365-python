# Copyright (c) Microsoft. All rights reserved.

"""
Microsoft Agent 365 Notifications

Notification and messaging extensions for AI agent applications.
This module provides utilities for handling agent notifications and routing.
"""

# Main notification handler class
from .agent_notification import (
    AgentNotification,
    AgentHandler,
)

# Import all models from the models subpackage
from .models import (
    AgentNotificationActivity,
    EmailReference,
    WpxComment,
    EmailResponse,
    NotificationTypes,
    AgentSubChannel,
    AgentLifecycleEvent,
)

__all__ = [
    # Main notification handler
    "AgentNotification",
    "AgentHandler",
    # Models and data classes
    "AgentNotificationActivity",
    "EmailReference",
    "WpxComment",
    "EmailResponse",
    "NotificationTypes",
    "AgentSubChannel",
    "AgentLifecycleEvent",
]

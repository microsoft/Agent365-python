# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class NotificationTypes(str, Enum):
    """Enumeration of notification types supported by Agent 365.

    This enum defines the different types of notifications that agents can receive
    from Microsoft 365 applications and services.

    Attributes:
        EMAIL_NOTIFICATION: Notification related to email events in Outlook.
        WPX_COMMENT: Notification related to comments in Word, PowerPoint, or Excel.
        AGENT_LIFECYCLE: Notification related to agent lifecycle events such as user
            creation, deletion, or workload onboarding updates.
    """

    EMAIL_NOTIFICATION = "emailNotification"
    WPX_COMMENT = "wpxComment"
    AGENT_LIFECYCLE = "agentLifecycle"

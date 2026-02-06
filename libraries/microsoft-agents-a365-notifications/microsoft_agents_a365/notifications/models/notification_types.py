# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class NotificationTypes(str, Enum):
    EMAIL_NOTIFICATION = "emailNotification"
    WPX_COMMENT = "wpxComment"
    AGENT_LIFECYCLE = "agentLifecycle"

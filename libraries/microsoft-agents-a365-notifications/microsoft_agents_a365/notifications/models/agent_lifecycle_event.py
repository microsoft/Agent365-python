# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class AgentLifecycleEvent(str, Enum):
    """Enumeration of agent lifecycle event types.

    This enum defines the different lifecycle events that can occur for agentic user
    identities in the Microsoft 365 ecosystem.

    Attributes:
        USERCREATED: Event triggered when a new agentic user identity is created.
        USERWORKLOADONBOARDINGUPDATED: Event triggered when a user's workload
            onboarding status is updated.
        USERDELETED: Event triggered when an agentic user identity is deleted.
    """

    USERCREATED = "agenticuseridentitycreated"
    USERWORKLOADONBOARDINGUPDATED = "agenticuserworkloadonboardingupdated"
    USERDELETED = "agenticuseridentitydeleted"

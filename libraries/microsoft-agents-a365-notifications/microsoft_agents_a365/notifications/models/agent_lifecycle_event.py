# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class AgentLifecycleEvent(str, Enum):
    USERCREATED = "agenticuseridentitycreated"
    USERWORKLOADONBOARDINGUPDATED = "agenticuserworkloadonboardingupdated"
    USERDELETED = "agenticuseridentitydeleted"

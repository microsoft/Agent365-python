# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class AgentSubChannel(str, Enum):
    """Enumeration of agent subchannels within Microsoft 365 applications.

    This enum defines the different subchannels through which agents can receive
    notifications and messages from specific Microsoft 365 applications.

    Attributes:
        EMAIL: Email subchannel for Outlook-related notifications.
        EXCEL: Excel subchannel for spreadsheet-related notifications.
        WORD: Word subchannel for document-related notifications.
        POWERPOINT: PowerPoint subchannel for presentation-related notifications.
        FEDERATED_KNOWLEDGE_SERVICE: Federated Knowledge Service subchannel for
            knowledge graph and search-related notifications.
    """

    EMAIL = "email"
    EXCEL = "excel"
    WORD = "word"
    POWERPOINT = "powerpoint"
    FEDERATED_KNOWLEDGE_SERVICE = "federatedknowledgeservice"

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class AgentType(Enum):
    """
    Supported agent types for generative AI.
    """

    ENTRA_EMBODIED = "EntraEmbodied"
    """Entra embodied agent."""

    ENTRA_NON_EMBODIED = "EntraNonEmbodied"
    """Entra non-embodied agent."""

    MICROSOFT_COPILOT = "MicrosoftCopilot"
    """Microsoft Copilot agent."""

    DECLARATIVE_AGENT = "DeclarativeAgent"
    """Declarative agent."""

    FOUNDRY = "Foundry"
    """Foundry agent."""

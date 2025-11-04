# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Optional

from .models.agent_type import AgentType


@dataclass
class AgentDetails:
    """Details about an AI agent in the system."""

    agent_id: str
    """The unique identifier for the AI agent."""

    agent_name: Optional[str] = None
    """The human-readable name of the AI agent."""

    agent_description: Optional[str] = None
    """A description of the AI agent's purpose or capabilities."""

    agent_auid: Optional[str] = None
    """Optional Agent User ID for the agent."""

    agent_upn: Optional[str] = None
    """Optional User Principal Name (UPN) for the agent."""

    agent_blueprint_id: Optional[str] = None
    """Optional Blueprint/Application ID for the agent."""

    agent_type: Optional[AgentType] = None
    """The agent type."""

    tenant_id: Optional[str] = None
    """Optional Tenant ID for the agent."""

    conversation_id: Optional[str] = None
    """Optional conversation ID for compatibility."""

    icon_uri: Optional[str] = None
    """Optional icon URI for the agent."""

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentDetails:
    """Details about an AI agent in the system."""

    agent_id: str
    """The unique identifier for the AI agent."""

    agent_name: Optional[str] = None
    """The human-readable name of the AI agent."""

    agent_description: Optional[str] = None
    """A description of the AI agent's purpose or capabilities."""

    agentic_user_id: Optional[str] = None
    """Agentic User ID for the agent."""

    agentic_user_email: Optional[str] = None
    """Email address for the agentic user."""

    agent_blueprint_id: Optional[str] = None
    """Blueprint/Application ID for the agent."""

    agent_platform_id: Optional[str] = None
    """Platform ID for the agent."""

    tenant_id: Optional[str] = None
    """Tenant ID for the agent."""

    icon_uri: Optional[str] = None
    """Optional icon URI for the agent."""

    provider_name: Optional[str] = None
    """The provider name (e.g., openai, anthropic)."""

    agent_version: Optional[str] = None
    """Optional version of the agent (e.g., "1.0.0", "2025-05-01")."""

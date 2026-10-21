# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Optional, Union

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

    # NOTE: Appended after all pre-existing fields (rather than inserted in the
    # middle) to preserve positional-argument compatibility for existing callers.
    agent_type: Optional[Union[AgentType, str]] = None
    """Type classification for the agent. Accepts an `AgentType` enum member or
    a raw string; enum members are normalized to their string `.value` when
    emitted as a span attribute or baggage entry."""

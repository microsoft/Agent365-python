# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..agent_details import AgentDetails

from .user_details import UserDetails


@dataclass
class CallerDetails:
    """Composite caller details for agent-to-agent (A2A) scenarios.

    Groups the human caller identity and the calling agent identity together.
    """

    user_details: Optional[UserDetails] = None
    """Details about the human user in the call chain."""

    caller_agent_details: Optional["AgentDetails"] = None
    """Details about the calling agent in A2A scenarios."""

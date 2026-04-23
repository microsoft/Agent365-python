# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserDetails:
    """Details about the human user that invoked an agent."""

    user_id: Optional[str] = None
    """The unique identifier for the user."""

    user_email: Optional[str] = None
    """The email address of the user."""

    user_name: Optional[str] = None
    """The human-readable name of the user."""

    user_client_ip: Optional[str] = None
    """The client IP address of the user."""

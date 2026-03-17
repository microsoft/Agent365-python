# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Optional


@dataclass
class CallerDetails:
    """Details about the caller that invoked an agent."""

    caller_id: Optional[str] = None
    """The unique identifier for the caller."""

    caller_upn: Optional[str] = None
    """The User Principal Name (UPN) of the caller."""

    caller_name: Optional[str] = None
    """The human-readable name of the caller."""

    caller_client_ip: Optional[str] = None
    """The client IP address of the caller."""

# Copyright (c) Microsoft. All rights reserved.

"""
Tooling Options model.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolOptions:
    """Configuration options for tooling operations."""

    #: Gets or sets the name of the orchestrator.
    orchestrator_name: Optional[str]

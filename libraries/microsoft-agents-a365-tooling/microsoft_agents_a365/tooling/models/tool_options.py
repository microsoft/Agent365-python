# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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

# Copyright (c) Microsoft. All rights reserved.

# Request class.

from dataclasses import dataclass

from .execution_type import ExecutionType
from .source_metadata import SourceMetadata


@dataclass
class Request:
    """Request details for agent execution."""

    content: str
    execution_type: ExecutionType
    session_id: str | None = None
    source_metadata: SourceMetadata | None = None

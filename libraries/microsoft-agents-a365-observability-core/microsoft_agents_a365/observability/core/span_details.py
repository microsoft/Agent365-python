# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from datetime import datetime

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind


@dataclass
class SpanDetails:
    """Groups span configuration for scope construction."""

    span_kind: SpanKind | None = None
    """Optional span kind override."""

    parent_context: Context | None = None
    """Optional OpenTelemetry Context used to link this span to an upstream operation."""

    start_time: datetime | None = None
    """Optional explicit start time as a datetime object."""

    end_time: datetime | None = None
    """Optional explicit end time as a datetime object."""

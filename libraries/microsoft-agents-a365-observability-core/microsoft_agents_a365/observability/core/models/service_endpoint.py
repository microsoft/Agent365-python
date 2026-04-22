# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass


@dataclass
class ServiceEndpoint:
    """Represents a service endpoint with hostname and optional port."""

    hostname: str
    """The hostname of the service endpoint."""

    port: int | None = None
    """The port of the service endpoint."""

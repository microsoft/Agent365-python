# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Tenant details class.
from dataclasses import dataclass


@dataclass
class TenantDetails:
    """Represents the tenant id attached to the span."""

    tenant_id: str

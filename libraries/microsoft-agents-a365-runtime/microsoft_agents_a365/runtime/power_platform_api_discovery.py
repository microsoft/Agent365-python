# Copyright (c) Microsoft. All rights reserved.

import re
from typing import Literal

ClusterCategory = Literal[
    "local",
    "dev",
    "test",
    "preprod",
    "firstrelease",
    "prod",
    "gov",
    "high",
    "dod",
    "mooncake",
    "ex",
    "rx",
]


class PowerPlatformApiDiscovery:
    """Discovery helper for Power Platform API endpoints."""

    def __init__(self, cluster_category: ClusterCategory) -> None:
        self.cluster_category = cluster_category

    def get_token_audience(self) -> str:
        return f"https://{self._get_environment_api_host_name_suffix()}"

    def get_token_endpoint_host(self) -> str:
        return self._get_environment_api_host_name_suffix()

    def get_tenant_endpoint(self, tenant_id: str) -> str:
        return self._generate_power_platform_api_domain(tenant_id)

    def get_tenant_island_cluster_endpoint(self, tenant_id: str) -> str:
        return self._generate_power_platform_api_domain(tenant_id, "il-")

    def _generate_power_platform_api_domain(
        self, host_name_identifier: str, host_name_prefix: str = ""
    ) -> str:
        # Validate allowed characters: alphanumeric and dash
        if not re.match(r"^[a-zA-Z0-9-]+$", host_name_identifier):
            raise ValueError(
                f"Cannot generate Power Platform API endpoint because the tenant identifier contains invalid host name characters, only alphanumeric and dash characters are expected: {host_name_identifier}"
            )

        host_name_infix = "tenant"
        hex_name_suffix_length = self._get_hex_api_suffix_length()
        hex_name = host_name_identifier.lower().replace("-", "")

        if hex_name_suffix_length >= len(hex_name):
            raise ValueError(
                f"Cannot generate Power Platform API endpoint because the normalized tenant identifier must be at least {hex_name_suffix_length + 1} "
                f"characters in length: {hex_name}"
            )

        hex_name_suffix = hex_name[-hex_name_suffix_length:]
        hex_name_prefix = hex_name[: len(hex_name) - hex_name_suffix_length]
        host_name_suffix = self._get_environment_api_host_name_suffix()

        return f"{host_name_prefix}{hex_name_prefix}.{hex_name_suffix}.{host_name_infix}.{host_name_suffix}"

    def _get_hex_api_suffix_length(self) -> int:
        if self.cluster_category in ("firstrelease", "prod"):
            return 2
        return 1

    def _get_environment_api_host_name_suffix(self) -> str:
        cluster_to_suffix = {
            "local": "api.powerplatform.localhost",
            "dev": "api.powerplatform.com",  # defaulting to prod
            "test": "api.powerplatform.com",  # defaulting to prod
            "preprod": "api.powerplatform.com",  # defaulting to prod
            "firstrelease": "api.powerplatform.com",
            "prod": "api.powerplatform.com",
            "gov": "api.gov.powerplatform.microsoft.us",
            "high": "api.high.powerplatform.microsoft.us",
            "dod": "api.appsplatform.us",
            "mooncake": "api.powerplatform.partner.microsoftonline.cn",
            "ex": "api.powerplatform.eaglex.ic.gov",
            "rx": "api.powerplatform.microsoft.scloud",
        }
        cc = self.cluster_category
        try:
            return cluster_to_suffix[cc]
        except KeyError as exc:
            raise ValueError(f"Invalid ClusterCategory value: {self.cluster_category}") from exc

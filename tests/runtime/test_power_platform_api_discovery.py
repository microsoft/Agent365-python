# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for PowerPlatformApiDiscovery class."""

import pytest
from microsoft_agents_a365.runtime.power_platform_api_discovery import (
    PowerPlatformApiDiscovery,
)


# Tests for get_token_endpoint_host and get_token_audience
@pytest.mark.parametrize(
    "cluster,expected_host",
    [
        ("local", "api.powerplatform.localhost"),
        ("dev", "api.powerplatform.com"),
        ("test", "api.powerplatform.com"),
        ("preprod", "api.powerplatform.com"),
        ("firstrelease", "api.powerplatform.com"),
        ("prod", "api.powerplatform.com"),
        ("gov", "api.gov.powerplatform.microsoft.us"),
        ("high", "api.high.powerplatform.microsoft.us"),
        ("dod", "api.appsplatform.us"),
        ("mooncake", "api.powerplatform.partner.microsoftonline.cn"),
        ("ex", "api.powerplatform.eaglex.ic.gov"),
        ("rx", "api.powerplatform.microsoft.scloud"),
    ],
)
def test_host_suffix_and_audience(cluster, expected_host):
    """Test get_token_endpoint_host and get_token_audience return correct values for each cluster."""
    disc = PowerPlatformApiDiscovery(cluster)
    assert disc.get_token_endpoint_host() == expected_host
    assert disc.get_token_audience() == f"https://{expected_host}"


# Tests for _get_hex_api_suffix_length
@pytest.mark.parametrize(
    "cluster,expected_length",
    [
        ("prod", 2),
        ("firstrelease", 2),
        ("dev", 1),
        ("test", 1),
        ("preprod", 1),
        ("local", 1),
        ("gov", 1),
        ("high", 1),
        ("dod", 1),
        ("mooncake", 1),
        ("ex", 1),
        ("rx", 1),
    ],
)
def test_hex_suffix_length_rules(cluster, expected_length):
    """Test _get_hex_api_suffix_length returns correct suffix length for each cluster."""
    disc = PowerPlatformApiDiscovery(cluster)
    assert disc._get_hex_api_suffix_length() == expected_length


# Tests for get_tenant_endpoint
@pytest.mark.parametrize(
    "cluster,tenant_id,expected",
    [
        ("prod", "abc-012", "abc0.12.tenant.api.powerplatform.com"),
        ("dev", "A1B2", "a1b.2.tenant.api.powerplatform.com"),
        ("dev", "Ab-Cd-Ef", "abcde.f.tenant.api.powerplatform.com"),
    ],
)
def test_tenant_endpoint_generation(cluster, tenant_id, expected):
    """Test get_tenant_endpoint for various clusters and tenant IDs."""
    disc = PowerPlatformApiDiscovery(cluster)
    assert disc.get_tenant_endpoint(tenant_id) == expected


@pytest.mark.parametrize(
    "cluster,expected",
    [
        ("local", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.localhost"),
        ("dev", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("test", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("preprod", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("firstrelease", "e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com"),
        ("prod", "e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com"),
        ("gov", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.gov.powerplatform.microsoft.us"),
        ("high", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.high.powerplatform.microsoft.us"),
        ("dod", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.appsplatform.us"),
        (
            "mooncake",
            "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.partner.microsoftonline.cn",
        ),
        ("ex", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.eaglex.ic.gov"),
        ("rx", "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.microsoft.scloud"),
    ],
)
def test_tenant_endpoint_with_real_uuid(cluster, expected):
    """Test get_tenant_endpoint with real UUID across all clusters."""
    tenant_id = "e3064512-cc6d-4703-be71-a2ecaecaa98a"
    disc = PowerPlatformApiDiscovery(cluster)
    assert disc.get_tenant_endpoint(tenant_id) == expected


# Tests for get_tenant_island_cluster_endpoint
@pytest.mark.parametrize(
    "cluster,expected",
    [
        ("local", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.localhost"),
        ("dev", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("test", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("preprod", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com"),
        ("firstrelease", "il-e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com"),
        ("prod", "il-e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com"),
        ("gov", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.gov.powerplatform.microsoft.us"),
        ("high", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.high.powerplatform.microsoft.us"),
        ("dod", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.appsplatform.us"),
        (
            "mooncake",
            "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.partner.microsoftonline.cn",
        ),
        ("ex", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.eaglex.ic.gov"),
        ("rx", "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.microsoft.scloud"),
    ],
)
def test_tenant_island_cluster_endpoint(cluster, expected):
    """Test get_tenant_island_cluster_endpoint with real UUID across all clusters."""
    tenant_id = "e3064512-cc6d-4703-be71-a2ecaecaa98a"
    disc = PowerPlatformApiDiscovery(cluster)
    assert disc.get_tenant_island_cluster_endpoint(tenant_id) == expected


# Tests for error handling
@pytest.mark.parametrize(
    "tenant_id",
    [
        "invalid$name",
        "invalid?",
        "tenant@id",
        "tenant#123",
        "tenant with spaces",
        "",
        "---",
        "-",
    ],
)
def test_invalid_tenant_identifier(tenant_id):
    """Test ValueError is raised for invalid tenant IDs (invalid chars, empty, or all dashes)."""
    disc = PowerPlatformApiDiscovery("dev")
    with pytest.raises(ValueError):
        disc.get_tenant_endpoint(tenant_id)


@pytest.mark.parametrize(
    "cluster,tenant_id,min_length",
    [
        ("local", "a", 2),
        ("local", "a-", 2),
        ("prod", "aa", 3),
        ("prod", "a-a", 3),
    ],
)
def test_tenant_identifier_too_short(cluster, tenant_id, min_length):
    """Test ValueError is raised when tenant ID is too short after normalization."""
    disc = PowerPlatformApiDiscovery(cluster)
    with pytest.raises(ValueError, match=f"must be at least {min_length}"):
        disc.get_tenant_endpoint(tenant_id)

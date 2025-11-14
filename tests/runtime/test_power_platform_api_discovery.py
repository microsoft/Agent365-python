# Copyright (c) Microsoft. All rights reserved.

import unittest

from microsoft_agents_a365.runtime.power_platform_api_discovery import PowerPlatformApiDiscovery


class TestPowerPlatformApiDiscovery(unittest.TestCase):
    def test_host_suffix_and_audience(self):
        expected_host_suffixes = {
            "local": "api.powerplatform.localhost",
            "dev": "api.powerplatform.com",
            "test": "api.powerplatform.com",
            "preprod": "api.powerplatform.com",
            "firstrelease": "api.powerplatform.com",
            "prod": "api.powerplatform.com",
            "gov": "api.gov.powerplatform.microsoft.us",
            "high": "api.high.powerplatform.microsoft.us",
            "dod": "api.appsplatform.us",
            "mooncake": "api.powerplatform.partner.microsoftonline.cn",
            "ex": "api.powerplatform.eaglex.ic.gov",
            "rx": "api.powerplatform.microsoft.scloud",
        }

        for cluster, expected in expected_host_suffixes.items():
            with self.subTest(cluster=cluster):
                disc = PowerPlatformApiDiscovery(cluster)  # type: ignore[arg-type]
                self.assertEqual(disc.get_token_endpoint_host(), expected)
                self.assertEqual(disc.get_token_audience(), f"https://{expected}")

    def test_hex_suffix_length_rules(self):
        prod = PowerPlatformApiDiscovery("prod")
        first = PowerPlatformApiDiscovery("firstrelease")
        dev = PowerPlatformApiDiscovery("dev")

        self.assertEqual(prod._get_hex_api_suffix_length(), 2)
        self.assertEqual(first._get_hex_api_suffix_length(), 2)
        self.assertEqual(dev._get_hex_api_suffix_length(), 1)

    def test_tenant_endpoint_generation_prod(self):
        disc = PowerPlatformApiDiscovery("prod")
        tenant_id = "abc-012"  # normalized -> abc012; suffix length 2 -> '12'
        expected = "abc0.12.tenant.api.powerplatform.com"
        self.assertEqual(disc.get_tenant_endpoint(tenant_id), expected)

    def test_tenant_endpoint_generation_dev(self):
        disc = PowerPlatformApiDiscovery("dev")
        tenant_id = "A1B2"  # normalized -> a1b2; suffix length 1 -> '2'
        expected = "a1b.2.tenant.api.powerplatform.com"
        self.assertEqual(disc.get_tenant_endpoint(tenant_id), expected)

    def test_tenant_island_cluster_endpoint(self):
        disc = PowerPlatformApiDiscovery("prod")
        tenant_id = "abc-1234"  # normalized -> abc1234; suffix '34', prefix 'abc12'
        expected = "il-abc12.34.tenant.api.powerplatform.com"
        self.assertEqual(disc.get_tenant_island_cluster_endpoint(tenant_id), expected)

    def test_invalid_characters_in_tenant_identifier(self):
        disc = PowerPlatformApiDiscovery("dev")
        with self.assertRaisesRegex(ValueError, r"invalid host name characters"):
            disc.get_tenant_endpoint("invalid$name")

    def test_tenant_identifier_too_short_for_suffix(self):
        disc = PowerPlatformApiDiscovery("prod")
        # prod requires normalized length >= 3 (2 + 1). Provide only 2 characters.
        with self.assertRaisesRegex(ValueError, r"must be at least"):
            disc.get_tenant_endpoint("ab")

    def test_normalization_of_tenant_id(self):
        disc = PowerPlatformApiDiscovery("dev")
        tenant_id = "Ab-Cd-Ef"  # normalized -> abcdef; suffix 1 -> 'f', prefix 'abcde'
        expected = "abcde.f.tenant.api.powerplatform.com"
        self.assertEqual(disc.get_tenant_endpoint(tenant_id), expected)

    def test_nodejs_tenant_examples(self):
        tenant_id = "e3064512-cc6d-4703-be71-a2ecaecaa98a"
        expected_map = {
            "local": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.localhost",
            "dev": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "test": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "preprod": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "firstrelease": "e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com",
            "prod": "e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com",
            "gov": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.gov.powerplatform.microsoft.us",
            "high": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.high.powerplatform.microsoft.us",
            "dod": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.appsplatform.us",
            "mooncake": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.partner.microsoftonline.cn",
            "ex": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.eaglex.ic.gov",
            "rx": "e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.microsoft.scloud",
        }

        for cluster, expected in expected_map.items():
            with self.subTest(cluster=cluster):
                disc = PowerPlatformApiDiscovery(cluster)  # type: ignore[arg-type]
                self.assertEqual(disc.get_tenant_endpoint(tenant_id), expected)

    def test_nodejs_tenant_island_examples(self):
        tenant_id = "e3064512-cc6d-4703-be71-a2ecaecaa98a"
        expected_map = {
            "local": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.localhost",
            "dev": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "test": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "preprod": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.com",
            "firstrelease": "il-e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com",
            "prod": "il-e3064512cc6d4703be71a2ecaecaa9.8a.tenant.api.powerplatform.com",
            "gov": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.gov.powerplatform.microsoft.us",
            "high": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.high.powerplatform.microsoft.us",
            "dod": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.appsplatform.us",
            "mooncake": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.partner.microsoftonline.cn",
            "ex": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.eaglex.ic.gov",
            "rx": "il-e3064512cc6d4703be71a2ecaecaa98.a.tenant.api.powerplatform.microsoft.scloud",
        }

        for cluster, expected in expected_map.items():
            with self.subTest(cluster=cluster):
                disc = PowerPlatformApiDiscovery(cluster)  # type: ignore[arg-type]
                self.assertEqual(disc.get_tenant_island_cluster_endpoint(tenant_id), expected)

    def test_nodejs_invalid_characters_exact_message(self):
        disc = PowerPlatformApiDiscovery("local")
        expected_msg = "Cannot generate Power Platform API endpoint because the tenant identifier contains invalid host name characters, only alphanumeric and dash characters are expected: invalid?"
        with self.assertRaises(ValueError) as cm:
            disc.get_tenant_endpoint("invalid?")
        self.assertEqual(str(cm.exception), expected_msg)

    def test_nodejs_insufficient_length_exact_messages(self):
        disc_local = PowerPlatformApiDiscovery("local")
        with self.assertRaises(ValueError) as cm1:
            disc_local.get_tenant_endpoint("a")
        self.assertEqual(
            str(cm1.exception),
            "Cannot generate Power Platform API endpoint because the normalized tenant identifier must be at least 2 characters in length: a",
        )

        with self.assertRaises(ValueError) as cm2:
            disc_local.get_tenant_endpoint("a-")
        self.assertEqual(
            str(cm2.exception),
            "Cannot generate Power Platform API endpoint because the normalized tenant identifier must be at least 2 characters in length: a",
        )

        disc_prod = PowerPlatformApiDiscovery("prod")
        with self.assertRaises(ValueError) as cm3:
            disc_prod.get_tenant_endpoint("aa")
        self.assertEqual(
            str(cm3.exception),
            "Cannot generate Power Platform API endpoint because the normalized tenant identifier must be at least 3 characters in length: aa",
        )

        with self.assertRaises(ValueError) as cm4:
            disc_prod.get_tenant_endpoint("a-a")
        self.assertEqual(
            str(cm4.exception),
            "Cannot generate Power Platform API endpoint because the normalized tenant identifier must be at least 3 characters in length: aa",
        )


if __name__ == "__main__":
    unittest.main()

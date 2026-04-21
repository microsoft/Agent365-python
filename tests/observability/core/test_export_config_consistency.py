# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Snapshot tests for observability export configuration.

These tests pin the production export URL path and authentication scope together.
If the export URL path changes (e.g. from a backend migration), the scope must
be reviewed and updated in lockstep — and vice versa. A failure here is a
reminder to verify both values are consistent with the deployed backend.
"""

import unittest

from microsoft_agents_a365.observability.core.exporters.agent365_exporter import (
    DEFAULT_ENDPOINT_URL,
)
from microsoft_agents_a365.observability.core.exporters.utils import build_export_url
from microsoft_agents_a365.runtime.environment_utils import (
    PROD_OBSERVABILITY_SCOPE,
    get_observability_authentication_scope,
)


class TestExportConfigConsistency(unittest.TestCase):
    """Ensure export URL, endpoint, and auth scope stay in sync.

    These are intentionally pinned snapshot values. If any of the three
    production constants change (endpoint, scope, URL path), **all three
    tests below will likely need updating together**. That forced review is
    the whole point — it prevents one value from drifting without the others.
    """

    # ---- pinned production values ----

    EXPECTED_ENDPOINT = "https://agent365.svc.cloud.microsoft"
    EXPECTED_SCOPE = "api://9b975845-388f-4429-889e-eab1ef63949c/Agent365.Observability.OtelWrite"
    EXPECTED_STANDARD_PATH = "/observability/tenants/{tid}/otlp/agents/{aid}/traces"
    EXPECTED_S2S_PATH = "/observabilityService/tenants/{tid}/otlp/agents/{aid}/traces"

    # ---- snapshot assertions ----

    def test_default_endpoint_url(self):
        """DEFAULT_ENDPOINT_URL must match the expected production endpoint."""
        self.assertEqual(
            DEFAULT_ENDPOINT_URL,
            self.EXPECTED_ENDPOINT,
            "DEFAULT_ENDPOINT_URL changed — also review PROD_OBSERVABILITY_SCOPE "
            "and build_export_url() path. All three must stay in sync.",
        )

    def test_prod_observability_scope_value(self):
        """PROD_OBSERVABILITY_SCOPE must match the expected production scope."""
        self.assertEqual(
            PROD_OBSERVABILITY_SCOPE,
            self.EXPECTED_SCOPE,
            "PROD_OBSERVABILITY_SCOPE changed — also review DEFAULT_ENDPOINT_URL "
            "and build_export_url() path. All three must stay in sync.",
        )

    def test_export_url_standard_path_structure(self):
        """Standard export URL must use the pinned path pattern."""
        url = build_export_url(self.EXPECTED_ENDPOINT, "a1", "t1")
        expected = (
            f"{self.EXPECTED_ENDPOINT}"
            f"{self.EXPECTED_STANDARD_PATH.format(tid='t1', aid='a1')}?api-version=1"
        )
        self.assertEqual(
            url,
            expected,
            "Standard export URL path changed — also review PROD_OBSERVABILITY_SCOPE "
            "and DEFAULT_ENDPOINT_URL. All three must stay in sync.",
        )

    def test_export_url_s2s_path_structure(self):
        """S2S export URL must use the pinned path pattern."""
        url = build_export_url(self.EXPECTED_ENDPOINT, "a1", "t1", use_s2s_endpoint=True)
        expected = (
            f"{self.EXPECTED_ENDPOINT}"
            f"{self.EXPECTED_S2S_PATH.format(tid='t1', aid='a1')}?api-version=1"
        )
        self.assertEqual(
            url,
            expected,
            "S2S export URL path changed — also review PROD_OBSERVABILITY_SCOPE "
            "and DEFAULT_ENDPOINT_URL. All three must stay in sync.",
        )

    def test_scope_and_endpoint_are_coherent(self):
        """Auth scope and endpoint must both target the agent365 service.

        This is a coarse sanity check: if the endpoint domain changes away
        from 'agent365' but the scope still references the old AAD app, or
        vice versa, something is likely wrong.
        """
        scopes = get_observability_authentication_scope()
        self.assertEqual(len(scopes), 1)
        scope = scopes[0]

        # Scope should reference the Agent365 Observability permission
        self.assertIn("Agent365.Observability", scope)
        # Endpoint should be the agent365 service
        self.assertIn("agent365", DEFAULT_ENDPOINT_URL)


if __name__ == "__main__":
    unittest.main()

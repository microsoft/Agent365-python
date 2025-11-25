# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest

from microsoft_agents_a365.observability.core.utils import validate_and_normalize_ip


class TestUtils(unittest.TestCase):
    """Unit tests for utility functions."""

    def test_validate_and_normalize_ip(self):
        """Test validate_and_normalize_ip with various IP address scenarios."""
        # Valid IPv4 and IPv6 addresses
        self.assertEqual(validate_and_normalize_ip("192.168.1.1"), "192.168.1.1")
        self.assertEqual(validate_and_normalize_ip("2001:db8::1"), "2001:db8::1")

        # IPv6 normalization
        self.assertEqual(
            validate_and_normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001"), "2001:db8::1"
        )

        # Invalid IP addresses and edge cases
        self.assertIsNone(validate_and_normalize_ip("256.1.1.1"))
        self.assertIsNone(validate_and_normalize_ip("not.an.ip.address"))
        self.assertIsNone(validate_and_normalize_ip("2001:db8::g1"))
        self.assertIsNone(validate_and_normalize_ip(None))
        self.assertIsNone(validate_and_normalize_ip(""))


if __name__ == "__main__":
    unittest.main()

# Copyright (c) Microsoft. All rights reserved.

import os
import unittest
from unittest.mock import patch

from microsoft_agents_a365.observability.core.exporters.utils import (
    get_validated_domain_override,
    truncate_span,
)


class TestUtils(unittest.TestCase):
    """Unit tests for utility functions."""

    def test_truncate_span_if_needed(self):
        """Test truncate_span_if_needed with various span sizes."""
        # Small span - should return unchanged
        small_span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "small_span",
            "attributes": {"key1": "value1", "key2": "value2"},
        }
        result = truncate_span(small_span)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "small_span")
        self.assertEqual(result["attributes"]["key1"], "value1")

        # Large span with large payload attributes - should truncate attributes
        large_span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "large_span",
            "attributes": {
                "gen_ai.system": "openai",
                "gen_ai.request.model": "gpt-4",
                "gen_ai.response.model": "gpt-4",
                "gen_ai.input.messages": "x" * 150000,  # Large payload
                "gen_ai.output.messages": "y" * 150000,  # Large payload
                "gen_ai.sample.attribute": "x" * 250000,  # Large payload
                "small_attr": "small_value",
            },
        }
        result = truncate_span(large_span)
        self.assertIsNotNone(result)
        # The largest attributes should be truncated first
        self.assertEqual(result["attributes"]["gen_ai.input.messages"], "TRUNCATED")
        self.assertEqual(result["attributes"]["small_attr"], "small_value")  # Unchanged
        self.assertEqual(result["attributes"]["gen_ai.sample.attribute"], "TRUNCATED")

        # Extremely large span - should return truncated span even if still large
        extreme_span = {
            "traceId": "abc123",
            "spanId": "def456",
            "name": "extreme_span",
            "attributes": {f"attr_{i}": "x" * 10000 for i in range(100)},  # Many large attributes
            "events": [
                {"name": f"event_{i}", "attributes": {"data": "y" * 10000}} for i in range(50)
            ],
        }
        result = truncate_span(extreme_span)
        self.assertIsNotNone(result)  # Should always return a span, even if still large
        # All attributes should be truncated due to size
        for key in result["attributes"]:
            self.assertEqual(result["attributes"][key], "TRUNCATED")


class TestGetValidatedDomainOverride(unittest.TestCase):
    """Unit tests for get_validated_domain_override function."""

    def test_returns_none_when_env_var_not_set(self):
        """Test that function returns None when environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_returns_none_when_env_var_is_empty(self):
        """Test that function returns None when environment variable is empty."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": ""}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_returns_none_when_env_var_is_whitespace(self):
        """Test that function returns None when environment variable is only whitespace."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "   "}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_accepts_valid_domain(self):
        """Test that function accepts a valid domain without protocol."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "example.com"}):
            result = get_validated_domain_override()
            self.assertEqual(result, "example.com")

    def test_accepts_valid_domain_with_port(self):
        """Test that function accepts a valid domain with port."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "example.com:8080"}):
            result = get_validated_domain_override()
            self.assertEqual(result, "example.com:8080")

    def test_accepts_valid_https_url(self):
        """Test that function accepts a valid URL with https protocol."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "https://example.com"}):
            result = get_validated_domain_override()
            self.assertEqual(result, "https://example.com")

    def test_accepts_valid_http_url(self):
        """Test that function accepts a valid URL with http protocol."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "http://example.com"}):
            result = get_validated_domain_override()
            self.assertEqual(result, "http://example.com")

    def test_accepts_valid_http_url_with_port(self):
        """Test that function accepts a valid URL with http protocol and port."""
        with patch.dict(
            os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "http://localhost:8080"}
        ):
            result = get_validated_domain_override()
            self.assertEqual(result, "http://localhost:8080")

    def test_rejects_invalid_protocol(self):
        """Test that function rejects URLs with invalid protocols (not http/https)."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "ftp://example.com"}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_rejects_domain_with_path(self):
        """Test that function rejects domain-only format with path separator."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "example.com/path"}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_rejects_protocol_without_hostname(self):
        """Test that function rejects URLs with protocol but no hostname."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "https://"}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_rejects_malformed_url_http_colon(self):
        """Test that function rejects malformed URLs like 'http:8080' (missing slashes)."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "http:8080"}):
            result = get_validated_domain_override()
            self.assertIsNone(result)

    def test_rejects_malformed_url_https_colon(self):
        """Test that function rejects malformed URLs like 'https:443' (missing slashes)."""
        with patch.dict(os.environ, {"A365_OBSERVABILITY_DOMAIN_OVERRIDE": "https:443"}):
            result = get_validated_domain_override()
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

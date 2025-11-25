# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest

from microsoft_agents_a365.observability.core.exporters.utils import (
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


if __name__ == "__main__":
    unittest.main()

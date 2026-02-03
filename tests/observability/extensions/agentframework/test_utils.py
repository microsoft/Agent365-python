# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Agent Framework utils."""

import unittest

from microsoft_agents_a365.observability.extensions.agentframework.utils import (
    extract_content_as_string_list,
    extract_input_content,
    extract_output_content,
)


class TestAgentFrameworkUtils(unittest.TestCase):
    """Test suite for Agent Framework utility functions."""

    def test_extract_content_filters_text_by_role(self):
        """Test text extraction with role filtering, ignoring tool calls."""
        msgs = '[{"role": "user", "parts": [{"type": "text", "content": "Hi"}]}, {"role": "assistant", "parts": [{"type": "tool_call"}, {"type": "text", "content": "Hello"}]}]'
        self.assertEqual(extract_content_as_string_list(msgs), '["Hi", "Hello"]')
        self.assertEqual(extract_content_as_string_list(msgs, role_filter="user"), '["Hi"]')
        self.assertEqual(extract_input_content(msgs), '["Hi"]')
        self.assertEqual(extract_output_content(msgs), '["Hello"]')

    def test_handles_invalid_and_edge_cases(self):
        """Test invalid JSON and edge cases return appropriate values."""
        self.assertEqual(extract_content_as_string_list("invalid"), "invalid")
        self.assertEqual(extract_content_as_string_list('{"not": "list"}'), '{"not": "list"}')
        self.assertEqual(extract_content_as_string_list("[]"), "[]")
        self.assertEqual(extract_content_as_string_list('[{"role": "user"}]'), "[]")


if __name__ == "__main__":
    unittest.main()

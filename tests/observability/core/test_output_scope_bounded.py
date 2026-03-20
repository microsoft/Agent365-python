# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for bounded output messages in OutputScope."""

import unittest
from unittest.mock import MagicMock, patch

from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope


class TestOutputScopeBounded(unittest.TestCase):
    """Tests that OutputScope._output_messages list is properly bounded."""

    def _make_scope(self, initial_messages: list[str] | None = None) -> OutputScope:
        """Create an OutputScope with mocked dependencies."""
        agent_details = MagicMock()
        agent_details.agent_id = "test-agent"
        agent_details.agent_name = "Test Agent"
        agent_details.agent_description = None
        agent_details.platform_id = None
        agent_details.conversation_id = None
        agent_details.icon_uri = None
        agent_details.agent_auid = None
        agent_details.agent_upn = None
        agent_details.agent_blueprint_id = None

        tenant_details = MagicMock()
        tenant_details.tenant_id = "test-tenant"

        response = MagicMock()
        response.messages = initial_messages or ["hello"]

        with patch.object(OutputScope, "__init__", lambda self, *a, **kw: None):
            scope = OutputScope.__new__(OutputScope)
            scope._output_messages = list(response.messages)
            scope.set_tag_maybe = MagicMock()

        return scope

    def test_max_output_messages_default(self):
        """Default _MAX_OUTPUT_MESSAGES should be 5000."""
        self.assertEqual(OutputScope._MAX_OUTPUT_MESSAGES, 5000)

    def test_record_output_messages_within_limit(self):
        """Messages under the limit should not be truncated."""
        scope = self._make_scope(["initial"])
        scope.record_output_messages(["msg1", "msg2", "msg3"])
        self.assertEqual(len(scope._output_messages), 4)
        self.assertEqual(scope._output_messages, ["initial", "msg1", "msg2", "msg3"])

    def test_record_output_messages_exceeds_limit(self):
        """Messages exceeding the limit should be truncated to keep newest."""
        scope = self._make_scope([])
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 10

            # Add 15 messages
            scope.record_output_messages([f"msg_{i}" for i in range(15)])

            # Should be capped at 10 (keeping the newest)
            self.assertEqual(len(scope._output_messages), 10)
            # Oldest 5 should be gone, newest 10 should remain
            self.assertEqual(scope._output_messages[0], "msg_5")
            self.assertEqual(scope._output_messages[-1], "msg_14")
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max

    def test_record_output_messages_multiple_calls_capped(self):
        """Multiple calls to record_output_messages should stay bounded."""
        scope = self._make_scope([])
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 5

            for batch in range(4):
                scope.record_output_messages([f"batch{batch}_msg{i}" for i in range(3)])

            # Total of 12 messages added in 4 batches, should be capped at 5
            self.assertLessEqual(len(scope._output_messages), 5)
            # Latest messages should be from the last batches
            self.assertIn("batch3_msg2", scope._output_messages)
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max

    def test_record_output_messages_exactly_at_limit(self):
        """Messages exactly at the limit should not be truncated."""
        scope = self._make_scope([])
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 5
            scope.record_output_messages([f"msg_{i}" for i in range(5)])
            self.assertEqual(len(scope._output_messages), 5)
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max


if __name__ == "__main__":
    unittest.main()

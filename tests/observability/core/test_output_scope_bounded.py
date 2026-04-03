# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for bounded output messages in OutputScope."""

import unittest
from unittest.mock import MagicMock, patch

from microsoft_agents_a365.observability.core.models.messages import OutputMessage, TextPart
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope


class TestOutputScopeBounded(unittest.TestCase):
    """Tests that OutputScope._output_messages list is properly bounded."""

    def _make_scope(self, initial_messages: list[str] | None = None) -> OutputScope:
        """Create an OutputScope with mocked dependencies."""
        with patch.object(OutputScope, "__init__", lambda self, *a, **kw: None):
            scope = OutputScope.__new__(OutputScope)
            # Store as OutputMessage objects (matching the real implementation)
            scope._output_messages = [
                OutputMessage(role="assistant", parts=[TextPart(content=m)])
                for m in (initial_messages or ["hello"])
            ]
            scope._output_messages_dirty = False
            scope.set_tag_maybe = MagicMock()

        return scope

    @staticmethod
    def _text(msg: OutputMessage) -> str:
        """Extract text content from an OutputMessage."""
        return msg.parts[0].content  # type: ignore[union-attr]

    def test_max_output_messages_default(self):
        """Default _MAX_OUTPUT_MESSAGES should be 5000."""
        self.assertEqual(OutputScope._MAX_OUTPUT_MESSAGES, 5000)

    def test_record_output_messages_within_limit(self):
        """Messages under the limit should not be truncated."""
        scope = self._make_scope(["initial"])
        scope.record_output_messages(["msg1", "msg2", "msg3"])
        self.assertEqual(len(scope._output_messages), 4)
        texts = [self._text(m) for m in scope._output_messages]
        self.assertEqual(texts, ["initial", "msg1", "msg2", "msg3"])

    def test_record_output_messages_exceeds_limit(self):
        """Messages exceeding the limit should be truncated to keep newest."""
        scope = self._make_scope([])
        scope._output_messages = []  # start truly empty
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 10

            # Add 15 messages
            scope.record_output_messages([f"msg_{i}" for i in range(15)])

            # Should be capped at 10 (keeping the newest)
            self.assertEqual(len(scope._output_messages), 10)
            # Oldest 5 should be gone, newest 10 should remain
            self.assertEqual(self._text(scope._output_messages[0]), "msg_5")
            self.assertEqual(self._text(scope._output_messages[-1]), "msg_14")
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max

    def test_record_output_messages_multiple_calls_capped(self):
        """Multiple calls to record_output_messages should stay bounded."""
        scope = self._make_scope([])
        scope._output_messages = []  # start truly empty
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 5

            for batch in range(4):
                scope.record_output_messages([f"batch{batch}_msg{i}" for i in range(3)])

            # Total of 12 messages added in 4 batches, should be capped at 5
            self.assertLessEqual(len(scope._output_messages), 5)
            # Latest messages should be from the last batches
            texts = [self._text(m) for m in scope._output_messages]
            self.assertIn("batch3_msg2", texts)
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max

    def test_record_output_messages_exactly_at_limit(self):
        """Messages exactly at the limit should not be truncated."""
        scope = self._make_scope([])
        scope._output_messages = []  # start truly empty
        original_max = OutputScope._MAX_OUTPUT_MESSAGES
        try:
            OutputScope._MAX_OUTPUT_MESSAGES = 5
            scope.record_output_messages([f"msg_{i}" for i in range(5)])
            self.assertEqual(len(scope._output_messages), 5)
        finally:
            OutputScope._MAX_OUTPUT_MESSAGES = original_max


if __name__ == "__main__":
    unittest.main()

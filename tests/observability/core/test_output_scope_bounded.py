# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for OutputScope record_output_messages overwrite behavior."""

import json
import unittest
from unittest.mock import MagicMock, patch

from microsoft_agents_a365.observability.core.constants import GEN_AI_OUTPUT_MESSAGES_KEY
from microsoft_agents_a365.observability.core.models.messages import (
    MessageRole,
    OutputMessage,
    OutputMessages,
    TextPart,
)
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope


class TestOutputScopeOverwrite(unittest.TestCase):
    """Tests that OutputScope.record_output_messages overwrites (not accumulates)."""

    def _make_scope(self) -> OutputScope:
        """Create an OutputScope with mocked dependencies."""
        with patch.object(OutputScope, "__init__", lambda self, *a, **kw: None):
            scope = OutputScope.__new__(OutputScope)
            scope.set_tag_maybe = MagicMock()
            scope._span = MagicMock()
        return scope

    def test_record_overwrites_with_strings(self):
        """Calling record_output_messages with strings sets the attribute."""
        scope = self._make_scope()
        scope.record_output_messages(["Final response"])

        scope.set_tag_maybe.assert_called()
        call_args = scope.set_tag_maybe.call_args
        self.assertEqual(call_args[0][0], GEN_AI_OUTPUT_MESSAGES_KEY)
        parsed = json.loads(call_args[0][1])
        self.assertIsInstance(parsed, list)
        self.assertEqual(parsed[0]["parts"][0]["content"], "Final response")

    def test_record_overwrites_with_structured(self):
        """Calling record_output_messages with OutputMessages sets the attribute."""
        scope = self._make_scope()
        wrapper = OutputMessages(
            messages=[
                OutputMessage(
                    role=MessageRole.ASSISTANT,
                    parts=[TextPart(content="Structured")],
                )
            ]
        )
        scope.record_output_messages(wrapper)

        call_args = scope.set_tag_maybe.call_args
        parsed = json.loads(call_args[0][1])
        self.assertEqual(parsed[0]["parts"][0]["content"], "Structured")

    def test_record_overwrites_with_dict(self):
        """Calling record_output_messages with dict sets JSON directly."""
        scope = self._make_scope()
        scope.record_output_messages({"result": "tool output"})

        call_args = scope.set_tag_maybe.call_args
        parsed = json.loads(call_args[0][1])
        self.assertEqual(parsed["result"], "tool output")

    def test_second_call_replaces_first(self):
        """Second call to record_output_messages replaces the first."""
        scope = self._make_scope()
        scope.record_output_messages(["First"])
        scope.record_output_messages(["Second"])

        # Last call should have "Second", not "First"
        call_args = scope.set_tag_maybe.call_args
        parsed = json.loads(call_args[0][1])
        self.assertNotIn("First", call_args[0][1])
        self.assertEqual(parsed[0]["parts"][0]["content"], "Second")


if __name__ == "__main__":
    unittest.main()

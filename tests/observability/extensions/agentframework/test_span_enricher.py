# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Agent Framework span enricher."""

import json
import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_TOOL_ARGS_KEY,
    GEN_AI_TOOL_CALL_RESULT_KEY,
)
from microsoft_agents_a365.observability.extensions.agentframework.span_enricher import (
    AF_TOOL_CALL_ARGUMENTS_KEY,
    AF_TOOL_CALL_RESULT_KEY,
    enrich_agent_framework_span,
)


class TestAgentFrameworkSpanEnricher(unittest.TestCase):
    """Test suite for enrich_agent_framework_span function."""

    def test_invoke_agent_span_enrichment(self):
        """Test invoke_agent span maps messages to A365 versioned format."""
        span = Mock(
            name="invoke_agent Agent365Assistant",
            attributes={
                GEN_AI_INPUT_MESSAGES_KEY: '[{"role": "user", "parts": [{"type": "text", "content": "Compute 15 % 4"}]}]',
                GEN_AI_OUTPUT_MESSAGES_KEY: '[{"role": "assistant", "parts": [{"type": "tool_call", "id": "c1"}]}, {"role": "tool", "parts": [{"type": "tool_call_response"}]}, {"role": "assistant", "parts": [{"type": "text", "content": "Result is 3."}]}]',
            },
        )
        span.name = "invoke_agent Agent365Assistant"
        result = enrich_agent_framework_span(span)

        # Input should be versioned format with user message
        input_json = json.loads(result.attributes[GEN_AI_INPUT_MESSAGES_KEY])
        self.assertEqual(input_json["version"], "0.1.0")
        self.assertEqual(len(input_json["messages"]), 1)
        self.assertEqual(input_json["messages"][0]["role"], "user")
        self.assertEqual(input_json["messages"][0]["parts"][0]["content"], "Compute 15 % 4")

        # Output should be versioned format: tool_call (no name -> filtered) + tool response + text
        output_json = json.loads(result.attributes[GEN_AI_OUTPUT_MESSAGES_KEY])
        self.assertEqual(output_json["version"], "0.1.0")
        # tool_call with no name is filtered, tool_call_response with no id/response passes,
        # assistant text passes
        assistant_msgs = [m for m in output_json["messages"] if m["role"] == "assistant"]
        self.assertTrue(len(assistant_msgs) >= 1)
        # At least one assistant message should have a text part
        text_parts = [p for m in assistant_msgs for p in m["parts"] if p.get("type") == "text"]
        self.assertEqual(text_parts[0]["content"], "Result is 3.")

    def test_execute_tool_span_enrichment(self):
        """Test execute_tool span maps tool arguments and result to standard keys."""
        span = Mock(
            name="execute_tool calculate",
            attributes={
                AF_TOOL_CALL_ARGUMENTS_KEY: '{"expression": "2 + 2"}',
                AF_TOOL_CALL_RESULT_KEY: "Result is 4",
            },
        )
        span.name = "execute_tool calculate"
        result = enrich_agent_framework_span(span)
        self.assertEqual(result.attributes[GEN_AI_TOOL_ARGS_KEY], '{"expression": "2 + 2"}')
        self.assertEqual(result.attributes[GEN_AI_TOOL_CALL_RESULT_KEY], "Result is 4")

    def test_non_matching_and_edge_cases_return_original(self):
        """Test non-matching, None, and empty attribute spans return unchanged."""
        span = Mock(name="other_op", attributes={"key": "value"})
        span.name = "other_op"
        self.assertEqual(enrich_agent_framework_span(span), span)

        span.name = "invoke_agent Test"
        span.attributes = None
        self.assertEqual(enrich_agent_framework_span(span), span)

        span.attributes = {}
        self.assertEqual(enrich_agent_framework_span(span), span)


if __name__ == "__main__":
    unittest.main()

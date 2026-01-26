# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Semantic Kernel span enricher."""

import unittest
from unittest.mock import Mock

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.extensions.semantickernel.span_enricher import (
    enrich_semantic_kernel_span,
)


class TestSemanticKernelSpanEnricher(unittest.TestCase):
    """Test suite for enrich_semantic_kernel_span function."""

    def test_invoke_agent_span_extracts_content_from_messages(self):
        """Test that invoke_agent spans have content extracted from input/output messages."""
        # Create a mock span with invoke_agent name and message attributes
        mock_span = Mock()
        mock_span.name = "invoke_agent test-agent"
        mock_span.attributes = {
            "gen_ai.agent.invocation_input": '[{"role": "user", "content": "Hello"}]',
            "gen_ai.agent.invocation_output": '[{"role": "assistant", "content": "Hi there!"}]',
        }

        # Enrich the span
        enriched = enrich_semantic_kernel_span(mock_span)

        # Verify it returns an EnrichedReadableSpan with extracted content
        self.assertNotEqual(enriched, mock_span)
        attributes = enriched.attributes
        # extract_content_as_string_list returns a JSON string
        self.assertEqual(attributes[GEN_AI_INPUT_MESSAGES_KEY], '["Hello"]')
        self.assertEqual(attributes[GEN_AI_OUTPUT_MESSAGES_KEY], '["Hi there!"]')

    def test_non_matching_span_returns_original(self):
        """Test that spans not matching invoke_agent or execute_tool are returned unchanged."""
        # Create a mock span with a different operation name
        mock_span = Mock()
        mock_span.name = "some_other_operation"
        mock_span.attributes = {
            "some_key": "some_value",
        }

        # Enrich the span
        result = enrich_semantic_kernel_span(mock_span)

        # Verify it returns the original span unchanged
        self.assertEqual(result, mock_span)


if __name__ == "__main__":
    unittest.main()

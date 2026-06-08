# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


class GuardrailTargetType:
    """Well-known values for the type of content or action a guardrail is applied to.

    This is a free-form field per the OpenTelemetry semantic conventions.
    These class attributes provide discoverability for common values, but custom
    strings are also accepted when constructing GuardrailDetails.
    """

    LLM_INPUT = "llm_input"
    """Input to a language model."""

    LLM_OUTPUT = "llm_output"
    """Output from a language model."""

    TOOL_CALL = "tool_call"
    """A tool call action."""

    TOOL_DEFINITION = "tool_definition"
    """A tool definition."""

    MEMORY_STORE = "memory_store"
    """A memory store operation."""

    MEMORY_RETRIEVE = "memory_retrieve"
    """A memory retrieval operation."""

    KNOWLEDGE_QUERY = "knowledge_query"
    """A knowledge query."""

    KNOWLEDGE_RESULT = "knowledge_result"
    """A knowledge retrieval result."""

    MESSAGE = "message"
    """A message."""

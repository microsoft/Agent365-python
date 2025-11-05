# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time

import pytest
from microsoft_agents_a365.observability.core import configure, get_tracer_provider
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_SYSTEM_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.extensions.openai.trace_instrumentor import (
    OpenAIAgentsTraceInstrumentor,
)

try:
    from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool
    from openai import AsyncAzureOpenAI
except ImportError:
    pytest.skip(
        "OpenAI agents library and dependencies required for integration tests",
        allow_module_level=True,
    )


@function_tool
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    return a + b


@pytest.mark.integration
class TestOpenAITraceProcessorIntegration:
    """Integration tests for OpenAI trace processor with real Azure OpenAI."""

    def setup_method(self):
        """Set up test method with mock exporter."""
        self.captured_spans = []
        self.mock_exporter = MockAgent365Exporter(self.captured_spans)

    def test_openai_trace_processor_integration(self, azure_openai_config, agent365_config):
        """Test OpenAI trace processor with real Azure OpenAI call."""

        # Configure observability
        configure(
            service_name="integration-test-service",
            service_namespace="agent365-tests",
            logger_name="test-logger",
        )

        # Get the tracer provider and add our mock exporter
        provider = get_tracer_provider()
        provider.add_span_processor(self.mock_exporter)

        # Initialize the instrumentor
        instrumentor = OpenAIAgentsTraceInstrumentor()
        instrumentor.instrument()

        try:
            # Create Azure OpenAI client using API key (simpler for testing)
            openai_client = AsyncAzureOpenAI(
                api_key=azure_openai_config["api_key"],
                api_version=azure_openai_config["api_version"],
                azure_endpoint=azure_openai_config["endpoint"],
            )

            # Create agent with proper model configuration
            agent = Agent(
                name="TestAgent",
                instructions="You are a helpful assistant.",
                model=OpenAIChatCompletionsModel(
                    model=azure_openai_config["deployment"], openai_client=openai_client
                ),
            )

            # Execute a simple prompt using async runner
            import asyncio

            async def run_agent():
                result = await Runner.run(agent, "What can you do?")
                return result.final_output

            response = asyncio.run(run_agent())

            # Give some time for spans to be processed
            time.sleep(1)

            # Verify that spans were captured
            assert len(self.captured_spans) > 0, "No spans were captured"

            # Verify we have the expected span types
            span_names = [span.name for span in self.captured_spans]
            print(f"Captured spans: {span_names}")

            # Validate attributes on spans
            self._validate_span_attributes(agent365_config)

            # Verify the response content
            assert response is not None
            assert len(response) > 0
            print(f"Agent response: {response}")

        finally:
            # Clean up
            instrumentor.uninstrument()

    def test_openai_trace_processor_with_tool_calls(self, azure_openai_config, agent365_config):
        """Test OpenAI trace processor with tool calls."""

        # Configure observability
        configure(
            service_name="integration-test-service-tools",
            service_namespace="agent365-tests",
            logger_name="test-logger",
        )

        # Get the tracer provider and add our mock exporter
        provider = get_tracer_provider()
        provider.add_span_processor(self.mock_exporter)

        # Initialize the instrumentor
        instrumentor = OpenAIAgentsTraceInstrumentor()
        instrumentor.instrument()

        try:
            # Create Azure OpenAI client using API key
            openai_client = AsyncAzureOpenAI(
                api_key=azure_openai_config["api_key"],
                api_version=azure_openai_config["api_version"],
                azure_endpoint=azure_openai_config["endpoint"],
            )

            # Create agent with tool
            agent = Agent(
                name="MathAgent",
                instructions="You are a helpful math assistant. Use the add_numbers tool to perform calculations.",
                model=OpenAIChatCompletionsModel(
                    model=azure_openai_config["deployment"], openai_client=openai_client
                ),
                tools=[add_numbers],
            )

            # Execute a prompt that requires tool usage
            import asyncio

            async def run_agent_with_tool():
                result = await Runner.run(agent, "What is 15 + 27?")
                return result.final_output

            response = asyncio.run(run_agent_with_tool())

            # Give some time for spans to be processed
            time.sleep(1)

            # Verify that spans were captured
            assert len(self.captured_spans) > 0, "No spans were captured"

            # Verify we have the expected span types
            span_names = [span.name for span in self.captured_spans]
            print(f"Captured spans with tools: {span_names}")

            # Validate attributes on spans including tool calls
            self._validate_tool_span_attributes(agent365_config)

            # Verify the response content includes the calculation result
            assert response is not None
            assert len(response) > 0
            assert "42" in response  # 15 + 27 = 42
            print(f"Agent response with tool: {response}")

        finally:
            # Clean up
            instrumentor.uninstrument()

    def _validate_span_attributes(self, agent365_config):
        """Validate that spans have the expected attributes."""
        llm_spans_found = 0
        agent_spans_found = 0

        for span in self.captured_spans:
            attributes = dict(span.attributes or {})
            print(f"Span '{span.name}' attributes: {list(attributes.keys())}")

            # Check common attributes
            if TENANT_ID_KEY in attributes:
                assert attributes[TENANT_ID_KEY] == agent365_config["tenant_id"]

            if GEN_AI_AGENT_ID_KEY in attributes:
                assert attributes[GEN_AI_AGENT_ID_KEY] == agent365_config["agent_id"]

            # Check for LLM spans (generation spans)
            if GEN_AI_SYSTEM_KEY in attributes and attributes[GEN_AI_SYSTEM_KEY] == "openai":
                if GEN_AI_REQUEST_MODEL_KEY in attributes:
                    llm_spans_found += 1
                    # Validate LLM span attributes
                    assert GEN_AI_REQUEST_MODEL_KEY in attributes
                    assert attributes[GEN_AI_REQUEST_MODEL_KEY] is not None
                    print(f"✓ Found LLM span with model: {attributes[GEN_AI_REQUEST_MODEL_KEY]}")

                    # Check for input/output messages
                    if GEN_AI_INPUT_MESSAGES_KEY in attributes:
                        input_messages = attributes[GEN_AI_INPUT_MESSAGES_KEY]
                        assert input_messages is not None
                        print(f"✓ Input messages found: {input_messages[:100]}...")

                    if GEN_AI_OUTPUT_MESSAGES_KEY in attributes:
                        output_messages = attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
                        assert output_messages is not None
                        print(f"✓ Output messages found: {output_messages[:100]}...")

            # Check for agent spans
            if "agent" in span.name.lower():
                agent_spans_found += 1
                print(f"✓ Found agent span: {span.name}")

        # Ensure we found at least some spans with telemetry data
        assert len(self.captured_spans) > 0, "No spans were captured"
        print(f"✓ Captured {len(self.captured_spans)} spans total")
        print(f"✓ Found {llm_spans_found} LLM spans and {agent_spans_found} agent spans")

    def _validate_tool_span_attributes(self, agent365_config):
        """Validate that spans have the expected attributes including tool calls."""
        llm_spans_found = 0
        agent_spans_found = 0
        tool_spans_found = 0

        for span in self.captured_spans:
            attributes = dict(span.attributes or {})
            print(f"Span '{span.name}' attributes: {list(attributes.keys())}")

            # Check common attributes
            if TENANT_ID_KEY in attributes:
                assert attributes[TENANT_ID_KEY] == agent365_config["tenant_id"]

            if GEN_AI_AGENT_ID_KEY in attributes:
                assert attributes[GEN_AI_AGENT_ID_KEY] == agent365_config["agent_id"]

            # Check for LLM spans (generation spans)
            if GEN_AI_SYSTEM_KEY in attributes and attributes[GEN_AI_SYSTEM_KEY] == "openai":
                if GEN_AI_REQUEST_MODEL_KEY in attributes:
                    llm_spans_found += 1
                    print(f"✓ Found LLM span with model: {attributes[GEN_AI_REQUEST_MODEL_KEY]}")

                    # Check for tool calls in messages
                    if GEN_AI_OUTPUT_MESSAGES_KEY in attributes:
                        output_messages = attributes[GEN_AI_OUTPUT_MESSAGES_KEY]
                        if "tool_calls" in output_messages:
                            print("✓ Found tool calls in LLM output messages")

            # Check for agent spans
            if "agent" in span.name.lower():
                agent_spans_found += 1
                print(f"✓ Found agent span: {span.name}")

            # Check for tool execution spans
            if "execute_tool" in span.name.lower() or "calculator_tool" in span.name.lower():
                tool_spans_found += 1
                print(f"✓ Found tool execution span: {span.name}")

        # Ensure we found the expected span types
        assert len(self.captured_spans) > 0, "No spans were captured"
        print(f"✓ Captured {len(self.captured_spans)} spans total")
        print(
            f"✓ Found {llm_spans_found} LLM spans, {agent_spans_found} agent spans, and {tool_spans_found} tool spans"
        )


class MockAgent365Exporter:
    """Mock span processor that captures spans instead of sending them."""

    def __init__(self, captured_spans):
        self.captured_spans = captured_spans

    def on_start(self, span, parent_context=None):
        """Called when a span starts."""
        pass

    def on_end(self, span):
        """Called when a span ends."""
        self.captured_spans.append(span)

    def shutdown(self):
        """Mock shutdown."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Mock force flush."""
        return True

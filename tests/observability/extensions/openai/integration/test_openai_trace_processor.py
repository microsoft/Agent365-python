# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time

import pytest
from microsoft_agents_a365.observability.core import configure, get_tracer_provider
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    GEN_AI_REQUEST_MODEL_KEY,
    GEN_AI_SYSTEM_KEY,
    INVOKE_AGENT_OPERATION_NAME,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
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

    def test_invoke_agent_span_required_attributes(self, azure_openai_config, agent365_config):
        """Test that invoke_agent span has all required attributes per schema."""

        # Configure observability
        configure(
            service_name="integration-test-invoke-agent",
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
            # Create Azure OpenAI client
            openai_client = AsyncAzureOpenAI(
                api_key=azure_openai_config["api_key"],
                api_version=azure_openai_config["api_version"],
                azure_endpoint=azure_openai_config["endpoint"],
            )

            # Create agent
            agent = Agent(
                name="TestAgent",
                instructions="You are a helpful assistant. Answer briefly.",
                model=OpenAIChatCompletionsModel(
                    model=azure_openai_config["deployment"], openai_client=openai_client
                ),
            )

            # Execute agent wrapped with BaggageBuilder to provide required attributes
            import asyncio

            async def run_agent():
                with (
                    BaggageBuilder()
                    .agent_id("test-agent-id")
                    .agent_name("TestAgent")
                    .agent_auid("test-agent-auid")
                    .agent_upn("test-agent@test.com")
                    .agent_blueprint_id("test-blueprint-id")
                    .tenant_id("test-tenant-id")
                    .caller_id("test-caller-id")
                    .caller_name("Test Caller")
                    .caller_upn("test-caller@test.com")
                    .caller_client_ip("127.0.0.1")
                    .conversation_id("test-conversation-id")
                    .channel_name("test-channel")
                    .correlation_id("test-correlation-id")
                    .build()
                ):
                    result = await Runner.run(agent, "Say hello")
                    return result.final_output

            response = asyncio.run(run_agent())

            # Give time for spans to be processed
            time.sleep(1)

            # Find the invoke_agent span
            invoke_agent_span = None
            for span in self.captured_spans:
                if span.name.startswith(INVOKE_AGENT_OPERATION_NAME):
                    invoke_agent_span = span
                    break

            assert invoke_agent_span is not None, "invoke_agent span not found"
            attributes = dict(invoke_agent_span.attributes or {})

            print(f"invoke_agent span attributes: {list(attributes.keys())}")

            # Validate REQUIRED attributes (must be present)
            required_attributes = [
                GEN_AI_OPERATION_NAME_KEY,  # "gen_ai.operation.name" - Set by SDK
                GEN_AI_AGENT_ID_KEY,  # "gen_ai.agent.id"
                GEN_AI_AGENT_NAME_KEY,  # "gen_ai.agent.name"
                GEN_AI_EXECUTION_TYPE_KEY,  # "gen_ai.execution.type"
                GEN_AI_INPUT_MESSAGES_KEY,  # "gen_ai.input.messages"
                GEN_AI_OUTPUT_MESSAGES_KEY,  # "gen_ai.output.messages"
            ]

            missing_required = []
            for attr in required_attributes:
                if attr not in attributes:
                    missing_required.append(attr)
                else:
                    print(f"✓ Required attribute present: {attr} = {str(attributes[attr])[:50]}...")

            assert len(missing_required) == 0, f"Missing required attributes: {missing_required}"

            # Validate operation name value
            assert attributes[GEN_AI_OPERATION_NAME_KEY] == INVOKE_AGENT_OPERATION_NAME, (
                f"Expected operation name '{INVOKE_AGENT_OPERATION_NAME}', "
                f"got '{attributes[GEN_AI_OPERATION_NAME_KEY]}'"
            )

            # Validate agent name matches
            assert attributes[GEN_AI_AGENT_NAME_KEY] == "TestAgent", (
                f"Expected agent name 'TestAgent', got '{attributes[GEN_AI_AGENT_NAME_KEY]}'"
            )

            # Validate input/output messages are non-empty
            assert attributes[GEN_AI_INPUT_MESSAGES_KEY], "Input messages should not be empty"
            assert attributes[GEN_AI_OUTPUT_MESSAGES_KEY], "Output messages should not be empty"

            print("✓ All required invoke_agent span attributes validated")
            print(f"Agent response: {response}")

        finally:
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

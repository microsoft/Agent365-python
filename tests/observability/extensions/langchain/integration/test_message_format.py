# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Integration tests for LangChain message format mapping.

These tests use the real A365 observability pipeline:
  configure() → get_tracer_provider() → CustomLangChainInstrumentor
with a SpanCapturingExporter inside _EnrichingBatchSpanProcessor, then make
real Azure OpenAI calls via LangChain and capture the span attributes.

These tests verify the serialized gen_ai.input.messages / gen_ai.output.messages
structured array format emitted by the observability pipeline.
"""

import json
import time
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

try:
    from langchain_openai import AzureChatOpenAI
except ImportError:
    pytest.skip(
        "langchain-openai required for LangChain integration tests",
        allow_module_level=True,
    )

from microsoft_agents_a365.observability.core import configure, get_tracer_provider
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
)
from microsoft_agents_a365.observability.extensions.langchain import (
    CustomLangChainInstrumentor,
)


class SpanCapturingExporter(SpanExporter):
    """Exporter that collects spans in-memory after enrichment."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


@pytest.mark.integration
class TestLangChainMessageFormat:
    """Capture real LangChain span attributes and verify message structure."""

    @pytest.fixture(autouse=True)
    def setup_observability(self) -> None:
        """Set up A365 observability with CustomLangChainInstrumentor."""
        if not hasattr(TestLangChainMessageFormat, "_exporter"):
            configure(
                service_name="integration-test-langchain",
                service_namespace="agent365-tests",
                logger_name="test-logger",
            )

            exporter = SpanCapturingExporter()
            provider = get_tracer_provider()
            provider.add_span_processor(
                _EnrichingBatchSpanProcessor(
                    exporter,
                    max_queue_size=100,
                    schedule_delay_millis=100,
                    max_export_batch_size=100,
                )
            )

            # CustomLangChainInstrumentor calls instrument() in __init__
            instrumentor = CustomLangChainInstrumentor()

            TestLangChainMessageFormat._exporter = exporter
            TestLangChainMessageFormat._instrumentor = instrumentor

        self.exporter = TestLangChainMessageFormat._exporter
        self.exporter.spans.clear()

    @pytest.fixture
    def llm(self, azure_openai_config: dict[str, Any]) -> AzureChatOpenAI:
        """Create a real Azure OpenAI LangChain chat model."""
        return AzureChatOpenAI(
            azure_endpoint=azure_openai_config["endpoint"],
            api_key=azure_openai_config["api_key"],
            azure_deployment=azure_openai_config["deployment"],
            api_version=azure_openai_config["api_version"],
        )

    def _find_chat_spans(self) -> list[ReadableSpan]:
        """Find exported spans that have gen_ai.input.messages."""
        get_tracer_provider().force_flush()
        time.sleep(0.5)
        return [
            s
            for s in self.exporter.spans
            if s.attributes and GEN_AI_INPUT_MESSAGES_KEY in s.attributes
        ]

    @pytest.mark.asyncio
    async def test_simple_chat_message_mapping(self, llm: AzureChatOpenAI) -> None:
        """Simple chat: capture LangChain message format on exported spans."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content="You are a helpful assistant. Reply in one sentence."),
            HumanMessage(content="What is the capital of France?"),
        ]

        result = await llm.ainvoke(messages)
        assert result is not None
        assert len(result.content) > 0

        chat_spans = self._find_chat_spans()
        assert len(chat_spans) > 0, (
            f"No chat spans found. All spans: {[s.name for s in self.exporter.spans]}"
        )

        print(f"\n=== All exported spans ({len(self.exporter.spans)}) ===")
        for s in self.exporter.spans:
            attrs = dict(s.attributes or {})
            print(f"  {s.name} | attrs: {list(attrs.keys())}")

        attrs = dict(chat_spans[-1].attributes or {})

        # --- Input messages ---
        raw_input = attrs[GEN_AI_INPUT_MESSAGES_KEY]
        print(f"\n=== gen_ai.input.messages ===\n{raw_input}")
        input_data = json.loads(raw_input)

        # Verify structured array format
        assert isinstance(input_data, list)
        messages_list = input_data
        for msg in messages_list:
            assert "role" in msg
            assert "parts" in msg
        print("\n  ✓ Structured array format detected")

        # --- Output messages ---
        raw_output = attrs.get(GEN_AI_OUTPUT_MESSAGES_KEY)
        assert raw_output is not None, "gen_ai.output.messages not found"
        print(f"\n=== gen_ai.output.messages ===\n{raw_output}")
        output_data = json.loads(raw_output)

        assert isinstance(output_data, list)
        for msg in output_data:
            assert msg["role"] == "assistant"
            assert any(p["type"] == "text" for p in msg["parts"])
        print("\n  ✓ Structured array format detected")

    @pytest.mark.asyncio
    async def test_tool_call_message_mapping(self, llm: AzureChatOpenAI) -> None:
        """Tool-calling chat: capture tool_call parts in LangChain spans."""
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.tools import tool

        @tool
        def get_weather(city: str) -> str:
            """Get the current weather for a city."""
            return f"The weather in {city} is sunny, 22°C."

        llm_with_tools = llm.bind_tools([get_weather])

        messages = [
            SystemMessage(content="You are a weather assistant. Always use the get_weather tool."),
            HumanMessage(content="What's the weather in Seattle?"),
        ]

        result = await llm_with_tools.ainvoke(messages)
        assert result is not None

        chat_spans = self._find_chat_spans()
        assert len(chat_spans) > 0

        print(f"\n=== All exported spans ({len(self.exporter.spans)}) ===")
        for s in self.exporter.spans:
            attrs = dict(s.attributes or {})
            op = attrs.get(GEN_AI_OPERATION_NAME_KEY, "(none)")
            print(f"  {s.name} | op={op} | attrs: {list(attrs.keys())}")

        # Check all spans for message content
        for span in chat_spans:
            attrs = dict(span.attributes or {})
            for key in (GEN_AI_INPUT_MESSAGES_KEY, GEN_AI_OUTPUT_MESSAGES_KEY):
                raw = attrs.get(key)
                if raw:
                    print(f"\n--- {span.name} | {key} ---\n{raw}")

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Integration tests for AgentFramework message format mapping.

These tests use the real A365 observability pipeline:
  configure() → get_tracer_provider() → AgentFrameworkInstrumentor
with a SpanCapturingExporter inside _EnrichingBatchSpanProcessor, so spans
are captured after the enricher has run. This exercises the full code path:
  auto-instrumentation → enricher → mapper → serialize → export.
"""

import json
import time
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

# AgentFramework SDK
try:
    from agent_framework import RawAgent, tool
    from agent_framework.azure import AzureOpenAIChatClient
    from agent_framework.observability import enable_instrumentation
    from azure.identity import AzureCliCredential
except ImportError:
    pytest.skip(
        "AgentFramework library and dependencies required for integration tests",
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
from microsoft_agents_a365.observability.extensions.agentframework import (
    AgentFrameworkInstrumentor,
)


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to get weather for.

    Returns:
        A string describing the weather.
    """
    return f"The weather in {city} is sunny, 22°C."


class SpanCapturingExporter(SpanExporter):
    """Exporter that collects enriched spans in-memory.

    When used inside _EnrichingBatchSpanProcessor, spans arrive here
    after the registered enricher has already run.
    """

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
class TestAgentFrameworkMessageFormat:
    """Capture real AgentFramework span attributes after enrichment
    and verify the A365 structured array message format."""

    @pytest.fixture(autouse=True)
    def setup_observability(self) -> None:
        """Set up A365 observability with AgentFrameworkInstrumentor.

        A SpanCapturingExporter is attached via _EnrichingBatchSpanProcessor
        so that spans are captured after the enricher has run.
        """
        if not hasattr(TestAgentFrameworkMessageFormat, "_exporter"):
            configure(
                service_name="integration-test-message-format",
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

            enable_instrumentation(enable_sensitive_data=True)

            instrumentor = AgentFrameworkInstrumentor()
            instrumentor.instrument()

            TestAgentFrameworkMessageFormat._exporter = exporter
            TestAgentFrameworkMessageFormat._instrumentor = instrumentor

        self.exporter = TestAgentFrameworkMessageFormat._exporter
        self.exporter.spans.clear()

    @pytest.fixture
    def chat_client(self, azure_openai_config: dict[str, Any]) -> AzureOpenAIChatClient:
        """Create a real Azure OpenAI chat client."""
        return AzureOpenAIChatClient(
            endpoint=azure_openai_config["endpoint"],
            credential=AzureCliCredential(),
            deployment_name=azure_openai_config["deployment"],
            api_version=azure_openai_config["api_version"],
        )

    def _find_chat_spans(self) -> list[ReadableSpan]:
        """Find exported spans that have gen_ai.input.messages.

        Forces a flush so batched spans are exported before inspection.
        """
        get_tracer_provider().force_flush()
        time.sleep(0.5)
        return [
            s
            for s in self.exporter.spans
            if s.attributes and GEN_AI_INPUT_MESSAGES_KEY in s.attributes
        ]

    @pytest.mark.asyncio
    async def test_simple_chat_message_mapping(self, chat_client: AzureOpenAIChatClient) -> None:
        """Simple chat: verify exported spans contain structured A365 messages
        after enrichment (no manual mapper call)."""
        agent = RawAgent(
            client=chat_client,
            instructions="You are a helpful assistant. Reply in one sentence.",
            tools=[],
        )

        result = await agent.run("What is the capital of France?")
        assert result is not None
        assert len(result.text) > 0

        chat_spans = self._find_chat_spans()
        assert len(chat_spans) > 0, (
            f"No chat spans found. All spans: {[s.name for s in self.exporter.spans]}"
        )

        attrs = dict(chat_spans[-1].attributes or {})

        # --- Input messages: enriched to structured array format ---
        input_data = json.loads(attrs[GEN_AI_INPUT_MESSAGES_KEY])
        assert isinstance(input_data, list)
        messages = input_data

        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles
        for msg in messages:
            for part in msg["parts"]:
                assert "type" in part

        # --- Output messages: enriched to structured array format ---
        output_data = json.loads(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
        assert isinstance(output_data, list)
        out_messages = output_data

        assert out_messages[0]["role"] == "assistant"
        assert any(p["type"] == "text" for p in out_messages[0]["parts"])

        print(f"\n=== Enriched input ===\n{json.dumps(input_data, indent=2)}")
        print(f"\n=== Enriched output ===\n{json.dumps(output_data, indent=2)}")

    @pytest.mark.asyncio
    async def test_tool_call_message_mapping(self, chat_client: AzureOpenAIChatClient) -> None:
        """Tool-calling chat: verify tool_call and tool_call_response parts
        survive enrichment in exported spans."""
        agent = RawAgent(
            client=chat_client,
            instructions="You are a weather assistant. Always use the get_weather function.",
            tools=[get_weather],
        )

        result = await agent.run("What's the weather in Seattle?")
        assert result is not None
        assert len(result.text) > 0

        chat_spans = self._find_chat_spans()
        assert len(chat_spans) > 0

        print(f"\n=== All exported spans ({len(self.exporter.spans)}) ===")
        for s in self.exporter.spans:
            op = (s.attributes or {}).get(GEN_AI_OPERATION_NAME_KEY, "(none)")
            print(f"  {s.name} | op={op}")

        # Collect part types from exported (enriched) spans
        part_types: set[str] = set()
        for span in chat_spans:
            attrs = dict(span.attributes or {})
            for key in (GEN_AI_INPUT_MESSAGES_KEY, GEN_AI_OUTPUT_MESSAGES_KEY):
                raw = attrs.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                if isinstance(data, list):
                    messages = data
                    for msg in messages:
                        for part in msg.get("parts", []):
                            part_types.add(part.get("type", ""))

        assert "tool_call" in part_types, f"Expected tool_call in exported parts: {part_types}"
        assert "tool_call_response" in part_types, (
            f"Expected tool_call_response in exported parts: {part_types}"
        )
        print(f"\n  Exported part types: {part_types}")

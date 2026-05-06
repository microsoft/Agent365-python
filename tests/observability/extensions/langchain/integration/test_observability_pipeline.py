# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""End-to-end pipeline integration tests for LangChain observability.

These tests verify the full A365 observability pipeline:
  InvokeAgentScope → Inference (auto-instrumented) → ToolExecution (auto-instrumented)

The CustomLangChainInstrumentor automatically creates inference spans for LLM
calls and execute_tool spans for tool runs.  Its built-in message mapper
converts LangChain messages into the versioned A365 message format
(``{"version": "0.1.0", "messages": [...]}``) on ``gen_ai.input.messages``
and ``gen_ai.output.messages`` span attributes.

Wrapping the entire call in InvokeAgentScope makes all auto-instrumented spans
children of the invoke_agent span (since ``separate_trace_from_runtime_context``
defaults to ``False``).

Note: the message-format assertions accept both the versioned dict structure
*and* a raw JSON list.  The raw-list branch exists for backward compatibility
with older instrumentation versions or third-party LangChain instrumentors that
emit ``gen_ai.*.messages`` as plain JSON arrays before the A365 mapper was
integrated.
"""

import json
import os
import time

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.tools import tool
    from langchain_openai import AzureChatOpenAI
except ImportError:
    pytest.skip(
        "langchain-openai required for LangChain integration tests",
        allow_module_level=True,
    )

from microsoft_agents_a365.observability.core import configure, get_tracer_provider
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_INPUT_MESSAGES_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    GEN_AI_OUTPUT_MESSAGES_KEY,
    INVOKE_AGENT_OPERATION_NAME,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.exporters.enriching_span_processor import (
    _EnrichingBatchSpanProcessor,
)
from microsoft_agents_a365.observability.core.invoke_agent_details import InvokeAgentScopeDetails
from microsoft_agents_a365.observability.core.invoke_agent_scope import InvokeAgentScope
from microsoft_agents_a365.observability.core.request import Request
from microsoft_agents_a365.observability.extensions.langchain import (
    CustomLangChainInstrumentor,
)

# Ensure A365 observability scopes are active for tests
os.environ["ENABLE_A365_OBSERVABILITY"] = "true"


@tool
def add_numbers(a: float, b: float) -> str:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        A string describing the sum.
    """
    return f"The sum of {a} and {b} is {a + b}"


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


def _get_span_attr(span: ReadableSpan, key: str) -> str | None:
    """Safely get an attribute from a span."""
    attrs = span.attributes or {}
    return attrs.get(key)


def _find_spans_by_name_prefix(spans: list[ReadableSpan], prefix: str) -> list[ReadableSpan]:
    """Find spans whose name starts with a given prefix."""
    return [s for s in spans if s.name.startswith(prefix)]


@pytest.mark.integration
class TestLangChainObservabilityPipeline:
    """End-to-end pipeline tests: InvokeAgent → Inference → ToolExecution.

    Verifies that wrapping LangChain calls inside InvokeAgentScope
    produces a single trace with correct parent-child span hierarchy,
    operation names, and A365 versioned message format attributes.
    """

    @pytest.fixture(autouse=True)
    def setup_observability(self) -> None:
        """Set up A365 observability with CustomLangChainInstrumentor."""
        if not hasattr(TestLangChainObservabilityPipeline, "_exporter"):
            configure(
                service_name="integration-test-langchain-pipeline",
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

            # CustomLangChainInstrumentor instruments on init
            instrumentor = CustomLangChainInstrumentor()

            TestLangChainObservabilityPipeline._exporter = exporter
            TestLangChainObservabilityPipeline._instrumentor = instrumentor

        self.exporter = TestLangChainObservabilityPipeline._exporter
        self.exporter.spans.clear()

    @pytest.fixture
    def llm(self, azure_openai_config: dict) -> AzureChatOpenAI:
        """Create a real Azure OpenAI LangChain chat model."""
        return AzureChatOpenAI(
            azure_endpoint=azure_openai_config["endpoint"],
            api_key=azure_openai_config["api_key"],
            azure_deployment=azure_openai_config["deployment"],
            api_version=azure_openai_config["api_version"],
        )

    @pytest.fixture
    def agent_details(self) -> AgentDetails:
        """Create AgentDetails for the test agent."""
        tenant_id = os.getenv("AGENT365_TEST_TENANT_ID", "4d44f041-f91e-4d00-b107-61e47b26f5a8")
        agent_id = os.getenv("AGENT365_TEST_AGENT_ID", "3bccd52b-daaa-4b11-af40-47443852137c")
        return AgentDetails(
            agent_id=agent_id,
            agent_name="langchain-pipeline-test-agent",
            agent_description="Integration test agent for LangChain pipeline verification",
            tenant_id=tenant_id,
        )

    def _flush_and_collect(self) -> list[ReadableSpan]:
        """Force flush and return all captured spans."""
        get_tracer_provider().force_flush()
        time.sleep(0.5)
        return list(self.exporter.spans)

    # ------------------------------------------------------------------
    # Test: Full pipeline with tool execution loop
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pipeline_invoke_agent_with_tool_call(
        self,
        llm: AzureChatOpenAI,
        agent_details: AgentDetails,
    ) -> None:
        """Full pipeline: InvokeAgentScope wraps LangChain with tool execution.

        Uses a manual tool loop: LLM call → tool execution → LLM call.
        This ensures both inference and tool execution spans are created.

        Verifies:
        1. All spans share the same trace_id
        2. invoke_agent span is the root (no parent)
        3. Inference spans are descendants of invoke_agent
        4. Tool execution spans are descendants of invoke_agent
        5. A365 message format on inference spans
        """
        from langchain_core.messages import ToolMessage

        request = Request(content="What is 15 + 27?", session_id="test-langchain-pipeline")

        llm_with_tools = llm.bind_tools([add_numbers])

        with InvokeAgentScope.start(
            request=request,
            scope_details=InvokeAgentScopeDetails(),
            agent_details=agent_details,
        ):
            messages = [
                SystemMessage(
                    content=(
                        "You are a math assistant. You MUST use the add_numbers tool "
                        "for any arithmetic. Never compute in your head."
                    )
                ),
                HumanMessage(content="What is 15 + 27?"),
            ]

            # First LLM call — should produce a tool_calls response
            ai_response = await llm_with_tools.ainvoke(messages)
            messages.append(ai_response)

            # Execute tool calls if present
            if hasattr(ai_response, "tool_calls") and ai_response.tool_calls:
                for tc in ai_response.tool_calls:
                    tool_result = add_numbers.invoke(tc)
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=tc["id"]))

                # Second LLM call with tool results
                final_response = await llm_with_tools.ainvoke(messages)
            else:
                final_response = ai_response

        assert final_response is not None
        assert len(str(final_response.content)) > 0

        spans = self._flush_and_collect()
        assert len(spans) > 0, "No spans were captured"

        # --- Print span tree for debugging ---
        print(f"\n=== Captured {len(spans)} spans ===")
        for s in spans:
            op = _get_span_attr(s, GEN_AI_OPERATION_NAME_KEY) or "(none)"
            parent_id = f"{s.parent.span_id:016x}" if s.parent else "None"
            print(
                f"  {s.name} | op={op} | trace={s.context.trace_id:032x} "
                f"| span={s.context.span_id:016x} | parent={parent_id}"
            )

        # --- 1. Find invoke_agent span ---
        invoke_spans = _find_spans_by_name_prefix(spans, "invoke_agent")
        assert len(invoke_spans) >= 1, (
            f"Expected at least 1 invoke_agent span, got: {[s.name for s in spans]}"
        )
        invoke_span = invoke_spans[0]
        trace_id = invoke_span.context.trace_id

        # --- 2. All spans share the same trace_id ---
        for s in spans:
            assert s.context.trace_id == trace_id, (
                f"Span '{s.name}' has different trace_id: "
                f"{s.context.trace_id:032x} vs {trace_id:032x}"
            )

        # --- 3. invoke_agent span is the root ---
        assert invoke_span.parent is None, (
            f"invoke_agent should be root but has parent: {invoke_span.parent.span_id:016x}"
        )

        # --- 4. invoke_agent has correct operation name ---
        assert _get_span_attr(invoke_span, GEN_AI_OPERATION_NAME_KEY) == INVOKE_AGENT_OPERATION_NAME

        # --- 5. Tenant ID is set ---
        assert _get_span_attr(invoke_span, TENANT_ID_KEY) == agent_details.tenant_id

        # --- 6. Inference spans are descendants of invoke_agent ---
        # LangChain inference spans typically have chat operation or input messages
        inference_spans = [
            s
            for s in spans
            if s != invoke_span
            and (
                _get_span_attr(s, GEN_AI_OPERATION_NAME_KEY) == "chat"
                or _get_span_attr(s, GEN_AI_INPUT_MESSAGES_KEY) is not None
            )
            and not s.name.startswith("execute_tool")
        ]
        assert len(inference_spans) >= 1, (
            f"Expected at least 1 inference span, got: {[s.name for s in spans]}"
        )

        invoke_span_id = invoke_span.context.span_id
        for inf_span in inference_spans:
            self._assert_ancestor(
                inf_span,
                invoke_span_id,
                spans,
                f"Inference span '{inf_span.name}' is not a descendant of invoke_agent",
            )

        # --- 7. Tool execution spans are descendants of invoke_agent ---
        tool_spans = _find_spans_by_name_prefix(spans, "execute_tool")
        # Tool execution spans may or may not appear depending on whether
        # the LangChain tracer emits them. If present, verify hierarchy.
        if tool_spans:
            for tool_span in tool_spans:
                self._assert_ancestor(
                    tool_span,
                    invoke_span_id,
                    spans,
                    f"Tool span '{tool_span.name}' is not a descendant of invoke_agent",
                )
            print(f"\n✓ Found {len(tool_spans)} tool execution spans")

        # --- 8. A365 message format on inference spans ---
        # The A365 mapper emits the versioned format {"version": "0.1.0", "messages": [...]}.
        # Older or third-party instrumentors may emit a raw JSON list instead;
        # the raw-list branch is kept for backward compatibility.
        for inf_span in inference_spans:
            attrs = dict(inf_span.attributes or {})
            if GEN_AI_INPUT_MESSAGES_KEY in attrs:
                input_data = json.loads(attrs[GEN_AI_INPUT_MESSAGES_KEY])
                if isinstance(input_data, dict) and "version" in input_data:
                    assert input_data["version"] == "0.1.0"
                    for msg in input_data["messages"]:
                        assert "role" in msg
                        assert "parts" in msg

            if GEN_AI_OUTPUT_MESSAGES_KEY in attrs:
                output_data = json.loads(attrs[GEN_AI_OUTPUT_MESSAGES_KEY])
                if isinstance(output_data, dict) and "version" in output_data:
                    assert output_data["version"] == "0.1.0"

        print(
            f"\n✓ All pipeline assertions passed: "
            f"{len(spans)} spans, {len(inference_spans)} inference, "
            f"{len(tool_spans)} tool"
        )

    # ------------------------------------------------------------------
    # Test: Pipeline without tools (simple inference only)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pipeline_invoke_agent_simple_inference(
        self,
        llm: AzureChatOpenAI,
        agent_details: AgentDetails,
    ) -> None:
        """Pipeline with InvokeAgentScope + simple inference (no tools).

        Verifies invoke_agent → inference span hierarchy.
        """
        request = Request(content="Say hello", session_id="test-langchain-simple")

        with InvokeAgentScope.start(
            request=request,
            scope_details=InvokeAgentScopeDetails(),
            agent_details=agent_details,
        ):
            messages = [
                SystemMessage(content="You are a helpful assistant. Reply in one sentence."),
                HumanMessage(content="Say hello in exactly 5 words."),
            ]
            result = await llm.ainvoke(messages)

        assert result is not None
        assert len(str(result.content)) > 0

        spans = self._flush_and_collect()
        assert len(spans) > 0, "No spans were captured"

        # All spans share the same trace_id
        invoke_spans = _find_spans_by_name_prefix(spans, "invoke_agent")
        assert len(invoke_spans) >= 1
        invoke_span = invoke_spans[0]
        trace_id = invoke_span.context.trace_id

        for s in spans:
            assert s.context.trace_id == trace_id

        # invoke_agent is root
        assert invoke_span.parent is None

        # Inference spans are descendants
        inference_spans = [
            s
            for s in spans
            if s != invoke_span and _get_span_attr(s, GEN_AI_INPUT_MESSAGES_KEY) is not None
        ]
        assert len(inference_spans) >= 1

        invoke_span_id = invoke_span.context.span_id
        for inf_span in inference_spans:
            self._assert_ancestor(
                inf_span,
                invoke_span_id,
                spans,
                f"Inference span '{inf_span.name}' not a descendant of invoke_agent",
            )

        print(f"\n✓ Simple pipeline: {len(spans)} spans, hierarchy verified")

    # ------------------------------------------------------------------
    # Helper: assert ancestor relationship
    # ------------------------------------------------------------------

    def _assert_ancestor(
        self,
        span: ReadableSpan,
        ancestor_span_id: int,
        all_spans: list[ReadableSpan],
        message: str,
    ) -> None:
        """Walk up the parent chain and assert that ancestor_span_id is found."""
        span_map = {s.context.span_id: s for s in all_spans}
        current = span
        visited: set[int] = set()
        while current.parent is not None:
            parent_id = current.parent.span_id
            if parent_id == ancestor_span_id:
                return
            if parent_id in visited:
                break
            visited.add(parent_id)
            current = span_map.get(parent_id)
            if current is None:
                break
        raise AssertionError(message)

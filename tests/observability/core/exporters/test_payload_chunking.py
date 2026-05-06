# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for payload byte-size chunking in the Agent 365 exporter."""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from microsoft_agents_a365.observability.core.constants import (
    CHAT_OPERATION_NAME,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_OPERATION_NAME_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.exporters.agent365_exporter import (
    _Agent365Exporter,
)
from microsoft_agents_a365.observability.core.exporters.utils import (
    chunk_by_size,
    estimate_span_bytes,
    estimate_value_bytes,
    truncate_span,
)
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import StatusCode


def _make_otlp_span(attrs: dict, name: str = "test") -> dict:
    return {
        "traceId": "00000000000000000000000000000001",
        "spanId": "0000000000000002",
        "name": name,
        "kind": "INTERNAL",
        "startTimeUnixNano": 1000000000,
        "endTimeUnixNano": 2000000000,
        "attributes": attrs,
        "events": None,
        "links": None,
        "status": {"code": "UNSET", "message": ""},
    }


class TestEstimateSpanBytes(unittest.TestCase):
    def test_over_estimates_relative_to_actual_json_size(self) -> None:
        span = _make_otlp_span({
            "gen_ai.system": "openai",
            "gen_ai.tool.arguments": "x" * 1000,
            "gen_ai.tool.call_result": "y" * 1000,
        })
        actual = len(json.dumps(span).encode("utf-8"))
        self.assertGreaterEqual(estimate_span_bytes(span), actual)

    def test_grows_with_attribute_content(self) -> None:
        small = _make_otlp_span({"key": "val"})
        large = _make_otlp_span({"key": "x" * 10000})
        self.assertGreater(estimate_span_bytes(large), estimate_span_bytes(small))

    def test_accounts_for_events(self) -> None:
        base = _make_otlp_span({})
        with_events = {**base, "events": [{"name": "ev", "attributes": {"k": "v"}}]}
        self.assertGreater(estimate_span_bytes(with_events), estimate_span_bytes(base))


class TestEstimateValueBytes(unittest.TestCase):
    def test_handles_all_value_types(self) -> None:
        self.assertEqual(estimate_value_bytes("hello"), 40 + 5)
        self.assertEqual(estimate_value_bytes([]), 60)
        self.assertEqual(estimate_value_bytes(["a", "bb"]), 60 + (40 + 1) + (40 + 2))
        self.assertEqual(estimate_value_bytes([1, 2]), 60 + 50 * 2)
        self.assertEqual(estimate_value_bytes(True), 40)
        self.assertEqual(estimate_value_bytes(42), 40)
        self.assertEqual(estimate_value_bytes(None), 40)


class TestChunkBySize(unittest.TestCase):
    def _get_size(self, item: dict) -> int:
        return int(item["size"])

    def test_empty_input_returns_empty_output(self) -> None:
        self.assertEqual(chunk_by_size([], self._get_size, 900_000), [])

    def test_small_items_fit_in_one_chunk(self) -> None:
        items = [{"id": f"s{i}", "size": 100} for i in range(10)]
        chunks = chunk_by_size(items, self._get_size, 900_000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 10)

    def test_splits_when_cumulative_exceeds_limit_and_preserves_order(self) -> None:
        items = [{"id": f"s{i}", "size": 300_000} for i in range(5)]
        chunks = chunk_by_size(items, self._get_size, 900_000)
        self.assertGreaterEqual(len(chunks), 2)
        flat_ids = [item["id"] for chunk in chunks for item in chunk]
        self.assertEqual(flat_ids, ["s0", "s1", "s2", "s3", "s4"])

    def test_oversize_single_item_gets_its_own_chunk(self) -> None:
        chunks = chunk_by_size([{"id": "big", "size": 2_000_000}], self._get_size, 900_000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0]["id"], "big")

    def test_multi_item_chunks_respect_limit_no_chunk_is_empty(self) -> None:
        items = [{"id": f"s{i}", "size": 200_000} for i in range(5)]
        chunks = chunk_by_size(items, self._get_size, 500_000)
        for chunk in chunks:
            self.assertGreater(len(chunk), 0)
            if len(chunk) > 1:
                self.assertLessEqual(sum(item["size"] for item in chunk), 500_000)

    def test_rejects_zero_max_chunk_bytes(self) -> None:
        with self.assertRaises(ValueError):
            chunk_by_size([{"id": "s", "size": 1}], self._get_size, 0)

    def test_rejects_negative_max_chunk_bytes(self) -> None:
        with self.assertRaises(ValueError):
            chunk_by_size([{"id": "s", "size": 1}], self._get_size, -1)

    def test_rejects_negative_item_size(self) -> None:
        with self.assertRaises(ValueError):
            chunk_by_size([{"id": "s", "size": -1}], self._get_size, 100)


class TestTruncateSpanVerification(unittest.TestCase):
    MAX = 250 * 1024

    def test_leaves_small_span_unchanged(self) -> None:
        span = _make_otlp_span({"k": "small"})
        self.assertEqual(truncate_span(span)["attributes"]["k"], "small")

    def test_shrinks_oversize_span_below_limit(self) -> None:
        span = _make_otlp_span({"small": "ok", "fat": "x" * 300_000})
        result = truncate_span(span)
        self.assertLessEqual(len(json.dumps(result).encode("utf-8")), self.MAX)
        self.assertEqual(result["attributes"]["small"], "ok")
        self.assertEqual(result["attributes"]["fat"], "TRUNCATED")


class TestExporterChunking(unittest.TestCase):
    """End-to-end test: the exporter splits oversized batches into multiple HTTP requests."""

    def setUp(self) -> None:
        self.token_resolver = Mock(return_value="test_token")

    def _make_span(self, span_id: int, attribute_size: int) -> ReadableSpan:
        mock_span = Mock(spec=ReadableSpan)
        mock_span.name = f"span_{span_id}"

        ctx = Mock()
        ctx.trace_id = 0x1
        ctx.span_id = span_id
        mock_span.context = ctx
        mock_span.parent = None
        mock_span.start_time = 1640995200000000000
        mock_span.end_time = 1640995260000000000

        status = Mock()
        status.status_code = StatusCode.OK
        status.description = ""
        mock_span.status = status

        kind = Mock()
        kind.name = "INTERNAL"
        mock_span.kind = kind

        mock_span.attributes = {
            TENANT_ID_KEY: "tenant-1",
            GEN_AI_AGENT_ID_KEY: "agent-1",
            GEN_AI_OPERATION_NAME_KEY: CHAT_OPERATION_NAME,
            "payload": "x" * attribute_size,
        }
        mock_span.events = []
        mock_span.links = []

        scope = Mock()
        scope.name = "test.scope"
        scope.version = "1.0"
        mock_span.instrumentation_scope = scope

        resource = Mock()
        resource.attributes = {"service.name": "test"}
        mock_span.resource = resource
        return mock_span

    def test_oversized_batch_is_split_into_multiple_requests(self) -> None:
        exporter = _Agent365Exporter(
            token_resolver=self.token_resolver,
            cluster_category="test",
            max_payload_bytes=300_000,
        )

        # Each span carries ~200 KB of payload; with a 300 KB chunk limit,
        # 5 spans should yield at least 2 chunks.
        spans = [self._make_span(span_id=i + 1, attribute_size=200_000) for i in range(5)]

        with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
            result = exporter.export(spans)

        self.assertEqual(result, SpanExportResult.SUCCESS)
        self.assertGreaterEqual(mock_post.call_count, 2)

        # Each chunk body must be valid JSON with the expected envelope structure.
        total_spans_sent = 0
        for call in mock_post.call_args_list:
            url, body, headers = call.args
            data = json.loads(body)
            self.assertIn("resourceSpans", data)
            scope_spans = data["resourceSpans"][0]["scopeSpans"]
            for ss in scope_spans:
                total_spans_sent += len(ss["spans"])
        self.assertEqual(total_spans_sent, len(spans))

    def test_chunk_failure_short_circuits_remaining_chunks(self) -> None:
        exporter = _Agent365Exporter(
            token_resolver=self.token_resolver,
            cluster_category="test",
            max_payload_bytes=300_000,
        )
        spans = [self._make_span(span_id=i + 1, attribute_size=200_000) for i in range(5)]

        with patch.object(exporter, "_post_with_retries", return_value=False) as mock_post:
            result = exporter.export(spans)

        self.assertEqual(result, SpanExportResult.FAILURE)
        # First chunk fails; remaining chunks must not be sent.
        self.assertEqual(mock_post.call_count, 1)

    def test_small_batch_uses_single_request(self) -> None:
        exporter = _Agent365Exporter(
            token_resolver=self.token_resolver,
            cluster_category="test",
        )
        spans = [self._make_span(span_id=1, attribute_size=100)]

        with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
            result = exporter.export(spans)

        self.assertEqual(result, SpanExportResult.SUCCESS)
        self.assertEqual(mock_post.call_count, 1)


if __name__ == "__main__":
    unittest.main()

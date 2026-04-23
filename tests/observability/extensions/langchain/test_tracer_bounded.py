# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for bounded collections in the LangChain tracer."""

import unittest
from collections import OrderedDict
from unittest.mock import MagicMock, patch
from uuid import uuid4

from microsoft_agents_a365.observability.extensions.langchain.tracer import (
    CustomLangChainTracer,
)


class TestLangChainTracerBounded(unittest.TestCase):
    """Tests that LangChain tracer collections are properly bounded."""

    def _make_tracer(self) -> CustomLangChainTracer:
        """Create a tracer with a mock OTel tracer."""
        mock_otel_tracer = MagicMock()
        mock_span = MagicMock()
        mock_otel_tracer.start_span.return_value = mock_span
        return CustomLangChainTracer(
            tracer=mock_otel_tracer,
            separate_trace_from_runtime_context=True,
        )

    def test_spans_by_run_is_ordered_dict(self):
        """_spans_by_run should be an OrderedDict for bounded eviction."""
        tracer = self._make_tracer()
        self.assertIsInstance(tracer._spans_by_run, OrderedDict)

    def test_cap_ordered_dict_evicts_oldest(self):
        """_cap_ordered_dict should evict oldest entries (FIFO)."""
        d: OrderedDict[str, int] = OrderedDict()
        for i in range(15):
            d[f"key_{i}"] = i
        CustomLangChainTracer._cap_ordered_dict(d, 10)

        self.assertEqual(len(d), 10)
        # oldest 5 should be gone
        for i in range(5):
            self.assertNotIn(f"key_{i}", d)
        # newest 10 should remain
        for i in range(5, 15):
            self.assertIn(f"key_{i}", d)
            self.assertEqual(d[f"key_{i}"], i)

    def test_cap_ordered_dict_noop_when_under_limit(self):
        """_cap_ordered_dict should be a no-op when size is under limit."""
        d: OrderedDict[str, int] = OrderedDict()
        for i in range(5):
            d[f"key_{i}"] = i
        CustomLangChainTracer._cap_ordered_dict(d, 10)
        self.assertEqual(len(d), 5)

    def test_spans_by_run_bounded_on_start_trace(self):
        """_spans_by_run should be bounded when _start_trace adds entries."""
        tracer = self._make_tracer()
        # Use a small cap for testing
        original_max = CustomLangChainTracer._MAX_TRACKED_RUNS
        try:
            CustomLangChainTracer._MAX_TRACKED_RUNS = 5

            # Add more runs than the cap
            for i in range(10):
                run = MagicMock()
                run.id = uuid4()
                run.parent_run_id = None
                run.run_type = "llm"
                run.name = f"test_run_{i}"
                run.start_time = MagicMock()

                with patch(
                    "microsoft_agents_a365.observability.extensions.langchain.tracer"
                    ".context_api.get_value",
                    return_value=None,
                ):
                    tracer._start_trace(run)

            # Should be capped at 5
            self.assertLessEqual(len(tracer._spans_by_run), 5)
        finally:
            CustomLangChainTracer._MAX_TRACKED_RUNS = original_max

    def test_get_span_returns_none_for_missing(self):
        """get_span should return None for non-existent run_id."""
        tracer = self._make_tracer()
        result = tracer.get_span(uuid4())
        self.assertIsNone(result)

    def test_get_span_returns_span_for_existing(self):
        """get_span should return the span for existing run_id."""
        tracer = self._make_tracer()
        run_id = uuid4()
        mock_span = MagicMock()
        with tracer._lock:
            tracer._spans_by_run[run_id] = mock_span
        result = tracer.get_span(run_id)
        self.assertEqual(result, mock_span)

    def test_max_tracked_runs_default(self):
        """Default _MAX_TRACKED_RUNS should be 10000."""
        self.assertEqual(CustomLangChainTracer._MAX_TRACKED_RUNS, 10000)


if __name__ == "__main__":
    unittest.main()

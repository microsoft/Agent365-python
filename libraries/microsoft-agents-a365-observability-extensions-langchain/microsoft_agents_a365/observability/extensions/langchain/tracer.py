# Copyright (c) Microsoft. All rights reserved.

import logging
import re
from collections.abc import Iterator
from itertools import chain
from threading import RLock
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)
from uuid import UUID

from langchain_core.tracers import BaseTracer, LangChainTracer
from langchain_core.tracers.schemas import Run
from microsoft_agents_a365.observability.core.inference_operation_type import InferenceOperationType
from microsoft_agents_a365.observability.core.utils import (
    DictWithLock,
    as_utc_nano,
    flatten,
    record_exception,
)
from opentelemetry import context as context_api
from opentelemetry import trace as trace_api
from opentelemetry.context import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    get_value,
)
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue

from microsoft_agents_a365.observability.extensions.langchain.utils import (
    IGNORED_EXCEPTION_PATTERNS,
    add_operation_type,
    function_calls,
    input_messages,
    invocation_parameters,
    llm_provider,
    metadata,
    model_name,
    output_messages,
    prompts,
    token_counts,
    tools,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


CONTEXT_ATTRIBUTES = (
    "session.id",
    "user.id",
    "metadata",
    "tag.tags",
    "llm.prompt_template.template",
    "llm.prompt_template.variables",
    "llm.prompt_template.version",
)


class CustomLangChainTracer(BaseTracer):
    __slots__ = (
        "_tracer",
        "_separate_trace_from_runtime_context",
        "_spans_by_run",
    )

    def __init__(
        self,
        tracer: trace_api.Tracer,
        separate_trace_from_runtime_context: bool,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the OpenInferenceTracer.

        Args:
            tracer (trace_api.Tracer): The OpenTelemetry tracer for creating spans.
            separate_trace_from_runtime_context (bool): When True, always start a new trace for each
                span without a parent, isolating it from any existing trace in the runtime context.
            *args (Any): Positional arguments for BaseTracer.
            **kwargs (Any): Keyword arguments for BaseTracer.
        """
        super().__init__(*args, **kwargs)
        if TYPE_CHECKING:
            # check that `run_map` still exists in parent class
            assert self.run_map
        self.run_map = DictWithLock[str, Run](self.run_map)
        self._tracer = tracer
        self._separate_trace_from_runtime_context = separate_trace_from_runtime_context
        self._spans_by_run: dict[UUID, Span] = DictWithLock[UUID, Span]()
        self._lock = RLock()  # handlers may be run in a thread by langchain

    def get_span(self, run_id: UUID) -> Span | None:
        return self._spans_by_run.get(run_id)

    def _start_trace(self, run: Run) -> None:
        self.run_map[str(run.id)] = run
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        with self._lock:
            parent_context = (
                trace_api.set_span_in_context(parent)
                if (parent_run_id := run.parent_run_id)
                and (parent := self._spans_by_run.get(parent_run_id))
                else (context_api.Context() if self._separate_trace_from_runtime_context else None)
            )
        # We can't use real time because the handler may be
        # called in a background thread.
        start_time_utc_nano = as_utc_nano(run.start_time)
        span = self._tracer.start_span(
            name=run.name,
            context=parent_context,
            start_time=start_time_utc_nano,
        )

        # The following line of code is commented out to serve as a reminder that in a system
        # of callbacks, attaching the context can be hazardous because there is no guarantee
        # that the context will be detached. An error could happen between callbacks leaving
        # the context attached forever, and all future spans will use it as parent. What's
        # worse is that the error could have also prevented the span from being exported,
        # leaving all future spans as orphans. That is a very bad scenario.
        # token = context_api.attach(context)
        with self._lock:
            self._spans_by_run[run.id] = span

    def _end_trace(self, run: Run) -> None:
        self.run_map.pop(str(run.id), None)
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span = self._spans_by_run.pop(run.id, None)
        if span:
            try:
                _update_span(span, run)
            except Exception:
                logger.exception("Failed to update span with run data.")
            # We can't use real time because the handler may be
            # called in a background thread.
            end_time_utc_nano = as_utc_nano(run.end_time) if run.end_time else None
            span.end(end_time=end_time_utc_nano)

    def _persist_run(self, run: Run) -> None:
        pass

    def on_llm_error(self, error: BaseException, *args: Any, run_id: UUID, **kwargs: Any) -> Run:
        if span := self._spans_by_run.get(run_id):
            record_exception(span, error)
        return super().on_llm_error(error, *args, run_id=run_id, **kwargs)

    def on_chain_error(self, error: BaseException, *args: Any, run_id: UUID, **kwargs: Any) -> Run:
        if span := self._spans_by_run.get(run_id):
            record_exception(span, error)
        return super().on_chain_error(error, *args, run_id=run_id, **kwargs)

    def on_retriever_error(
        self, error: BaseException, *args: Any, run_id: UUID, **kwargs: Any
    ) -> Run:
        if span := self._spans_by_run.get(run_id):
            record_exception(span, error)
        return super().on_retriever_error(error, *args, run_id=run_id, **kwargs)

    def on_tool_error(self, error: BaseException, *args: Any, run_id: UUID, **kwargs: Any) -> Run:
        if span := self._spans_by_run.get(run_id):
            record_exception(span, error)
        return super().on_tool_error(error, *args, run_id=run_id, **kwargs)

    def on_chat_model_start(self, *args: Any, **kwargs: Any) -> Run:
        """
        This emulates the behavior of the LangChainTracer.
        https://github.com/langchain-ai/langchain/blob/c01467b1f4f9beae8f1edb105b17aa4f36bf6573/libs/core/langchain_core/tracers/langchain.py#L115

        Although this method exists on the parent class, i.e. `BaseTracer`,
        it requires setting `self._schema_format = "original+chat"`.
        https://github.com/langchain-ai/langchain/blob/c01467b1f4f9beae8f1edb105b17aa4f36bf6573/libs/core/langchain_core/tracers/base.py#L170

        But currently self._schema_format is marked for internal use.
        https://github.com/langchain-ai/langchain/blob/c01467b1f4f9beae8f1edb105b17aa4f36bf6573/libs/core/langchain_core/tracers/base.py#L60
        """  # noqa: E501
        return LangChainTracer.on_chat_model_start(self, *args, **kwargs)  # type: ignore


def get_attributes_from_context() -> Iterator[tuple[str, AttributeValue]]:
    for ctx_attr in CONTEXT_ATTRIBUTES:
        if (val := get_value(ctx_attr)) is not None:
            yield ctx_attr, cast(AttributeValue, val)


def _update_span(span: Span, run: Run) -> None:
    # If there  is no error or if there is an agent control exception, set the span to OK
    if run.error is None or any(
        re.match(pattern, run.error) for pattern in IGNORED_EXCEPTION_PATTERNS
    ):
        span.set_status(trace_api.StatusCode.OK)
    else:
        span.set_status(trace_api.Status(trace_api.StatusCode.ERROR, run.error))

    if run.run_type == "llm" and run.outputs.get("llm_output").get("id").startswith("chat"):
        span.update_name(f"{InferenceOperationType.CHAT.value.lower()} {span.name}")
    elif run.run_type.lower() == "tool":
        span.update_name(f"execute_tool {span.name}")
    span.set_attributes(dict(get_attributes_from_context()))
    span.set_attributes(
        dict(
            flatten(
                chain(
                    add_operation_type(run),
                    prompts(run.inputs),
                    input_messages(run.inputs),
                    output_messages(run.outputs),
                    invocation_parameters(run),
                    llm_provider(run.extra),
                    model_name(run.outputs, run.extra),
                    token_counts(run.outputs),
                    function_calls(run.outputs),
                    tools(run),
                    metadata(run),
                )
            )
        )
    )

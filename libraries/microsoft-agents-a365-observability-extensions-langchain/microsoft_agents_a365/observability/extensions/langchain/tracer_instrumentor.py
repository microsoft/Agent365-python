# Copyright (c) Microsoft. All rights reserved.

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any
from uuid import UUID

import langchain_core
import opentelemetry.trace as optel_trace
from langchain_core.callbacks import BaseCallbackManager
from microsoft_agents_a365.observability.core.config import (
    get_tracer,
    get_tracer_provider,
    is_configured,
)
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import Span
from wrapt import wrap_function_wrapper

from microsoft_agents_a365.observability.extensions.langchain.tracer import CustomLangChainTracer

_INSTRUMENTS: str = "langchain_core >= 0.1.0"


class CustomLangChainInstrumentor(BaseInstrumentor):
    """
    Minimal instrumentor that attaches a TraceForLangChain to every new
    LangChain BaseCallbackManager so runs produce OpenTelemetry spans.
    """

    def __init__(self) -> None:
        if not is_configured():
            raise RuntimeError(
                "Tracing SDK is not configured. Configure it before using this instrumentor."
            )
        super().__init__()
        self._tracer: CustomLangChainTracer | None = None
        self._original_cb_init: Callable[..., None] | None = None
        self.instrument()

    # ---- BaseInstrumentor API -------------------------------------------------

    def instrumentation_dependencies(self) -> Collection[str]:
        return (_INSTRUMENTS,)

    def _instrument(self, **kwargs: Any) -> None:
        tracer_name: str | None = kwargs.get("tracer_name")
        tracer_version: str | None = kwargs.get("tracer_version")

        # Prefer the Agent 365 tracer; fall back to OpenTelemetry’s default if needed.
        try:
            tracer = get_tracer(tracer_name, tracer_version)
        except Exception:
            tracer = optel_trace.get_tracer(tracer_name, tracer_version)

        # Ensure tracer provider exists (ignore returned value; side-effect is enough).
        try:
            get_tracer_provider()
        except Exception:
            optel_trace.get_tracer_provider()

        self._tracer = CustomLangChainTracer(
            tracer,
            bool(kwargs.get("separate_trace_from_runtime_context")),
        )

        # Save and wrap BaseCallbackManager.__init__ to attach the processor once per instance.
        self._original_cb_init = langchain_core.callbacks.BaseCallbackManager.__init__
        wrap_function_wrapper(
            module="langchain_core.callbacks",
            name="BaseCallbackManager.__init__",
            wrapper=_BaseCallbackManagerInit(self._tracer),
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        # Restore original constructor if we wrapped it.
        if self._original_cb_init is not None:
            langchain_core.callbacks.BaseCallbackManager.__init__ = self._original_cb_init  # type: ignore[assignment]
        self._original_cb_init = None
        self._tracer = None

    # ---- Helpers used by module-level functions -------------------------------

    def get_span(self, run_id: UUID) -> Span | None:
        """Return the span for a specific LangChain run_id, if available."""
        if not self._tracer:
            print("Missing tracer; call InstrumentorForLangChain().instrument() first.")
            return None
        # TraceForLangChain is expected to expose get_span(run_id).
        get_span_fn = getattr(self._tracer, "get_span", None)
        return get_span_fn(run_id) if callable(get_span_fn) else None

    def get_ancestors(self, run_id: UUID) -> list[Span]:
        """Return ancestor spans from the run’s parent up to the root (nearest first)."""
        if not self._tracer:
            print("Missing tracer; call InstrumentorForLangChain().instrument() first.")
            return []

        # Expect the processor to keep a run_map with parent linkage (string keys).
        run_map = getattr(self._tracer, "run_map", {}) or {}
        ancestors: list[Span] = []

        run = run_map.get(str(run_id))
        if not run:
            return ancestors

        ancestor_id = getattr(run, "parent_run_id", None)
        while ancestor_id:
            span = self.get_span(ancestor_id)
            if span:
                ancestors.append(span)
            run = run_map.get(str(ancestor_id))
            ancestor_id = getattr(run, "parent_run_id", None) if run else None

        return ancestors


class _BaseCallbackManagerInit:
    """Post-constructor hook that adds the TraceProcessor once (inheritable)."""

    __slots__ = ("_processor",)

    def __init__(self, processor: CustomLangChainTracer):
        self._processor = processor

    def __call__(
        self,
        wrapped: Callable[..., None],
        instance: BaseCallbackManager,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        wrapped(*args, **kwargs)  # run original __init__
        # Avoid duplicates: only add if a handler of the same type isn’t present.
        if not any(isinstance(h, type(self._processor)) for h in instance.inheritable_handlers):
            instance.add_handler(self._processor, inherit=True)


# ------------------------------ Convenience APIs ------------------------------


def _current_parent_run_id() -> UUID | None:
    """Best-effort: fetch current parent run_id from langchain runtime context."""
    config = langchain_core.runnables.config.var_child_runnable_config.get()
    if not isinstance(config, dict):
        return None
    for v in config.values():
        if isinstance(v, langchain_core.callbacks.BaseCallbackManager):
            if v.parent_run_id:
                return v.parent_run_id
    return None


def get_current_span() -> Span | None:
    """Return the current context’s parent span, if any."""
    run_id = _current_parent_run_id()
    if not run_id:
        return None
    return CustomLangChainInstrumentor().get_span(run_id)


def get_ancestor_spans() -> list[Span]:
    """
    Return ancestor spans for the current context (immediate parent → root).
    """
    run_id = _current_parent_run_id()
    if not run_id:
        return []
    return CustomLangChainInstrumentor().get_ancestors(run_id)

# Copyright (c) Microsoft. All rights reserved.

# pip install opentelemetry-sdk opentelemetry-api requests

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

import requests
from microsoft_agents_a365.runtime.power_platform_api_discovery import PowerPlatformApiDiscovery
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from .utils import (
    hex_span_id,
    hex_trace_id,
    kind_name,
    partition_by_identity,
    status_name,
    truncate_span,
)

# ---- Exporter ---------------------------------------------------------------

# Hardcoded constants - not configurable
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3

# Create logger for this module - inherits from 'microsoft_agents_a365.observability.core'
logger = logging.getLogger(__name__)


class Agent365Exporter(SpanExporter):
    """
    Agent 365 span exporter for Agent 365:
      * Partitions spans by (tenantId, agentId)
      * Builds OTLP-like JSON: resourceSpans -> scopeSpans -> spans
      * POSTs per group to https://{endpoint}/maven/agent365/agents/{agentId}/traces?api-version=1
      * Adds Bearer token via token_resolver(agentId, tenantId)
    """

    def __init__(
        self,
        token_resolver: Callable[[str, str], str | None],
        cluster_category: str = "prod",
        use_s2s_endpoint: bool = False,
    ):
        if token_resolver is None:
            raise ValueError("token_resolver must be provided.")
        self._session = requests.Session()
        self._closed = False
        self._lock = threading.Lock()
        self._token_resolver = token_resolver
        self._cluster_category = cluster_category
        self._use_s2s_endpoint = use_s2s_endpoint

    # ------------- SpanExporter API -----------------

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._closed:
            return SpanExportResult.FAILURE

        try:
            groups = partition_by_identity(spans)
            if not groups:
                # No spans with identity; treat as success
                logger.info("No spans with tenant/agent identity found; nothing exported.")
                return SpanExportResult.SUCCESS

            # Debug: Log number of groups and total span count
            total_spans = sum(len(activities) for activities in groups.values())
            logger.info(
                f"Found {len(groups)} identity groups with {total_spans} total spans to export"
            )

            any_failure = False
            for (tenant_id, agent_id), activities in groups.items():
                payload = self._build_export_request(activities)
                body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

                # Resolve endpoint + token
                discovery = PowerPlatformApiDiscovery(self._cluster_category)
                endpoint = discovery.get_tenant_island_cluster_endpoint(tenant_id)
                endpoint_path = (
                    f"/maven/agent365/service/agents/{agent_id}/traces"
                    if self._use_s2s_endpoint
                    else f"/maven/agent365/agents/{agent_id}/traces"
                )
                url = f"https://{endpoint}{endpoint_path}?api-version=1"

                # Debug: Log endpoint being used
                logger.info(
                    f"Exporting {len(activities)} spans to endpoint: {url} "
                    f"(tenant: {tenant_id}, agent: {agent_id})"
                )

                headers = {"content-type": "application/json"}
                try:
                    token = self._token_resolver(agent_id, tenant_id)
                    if token:
                        headers["authorization"] = f"Bearer {token}"
                        logger.info(f"Token resolved successfully for agent {agent_id}")
                    else:
                        logger.info(f"No token returned for agent {agent_id}")
                except Exception as e:
                    # If token resolution fails, treat as failure for this group
                    logger.error(
                        f"Token resolution failed for agent {agent_id}, tenant {tenant_id}: {e}"
                    )
                    any_failure = True
                    continue

                # Basic retry loop
                ok = self._post_with_retries(url, body, headers)
                if not ok:
                    any_failure = True

            return SpanExportResult.FAILURE if any_failure else SpanExportResult.SUCCESS

        except Exception as e:
            # Exporters should not raise; signal failure.
            logger.error(f"Export failed with exception: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._session.close()
            except Exception:
                pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    # ------------- HTTP helper ----------------------

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """Truncate text to a maximum length, adding '...' if truncated."""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def _post_with_retries(self, url: str, body: str, headers: dict[str, str]) -> bool:
        for attempt in range(DEFAULT_MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    url,
                    data=body.encode("utf-8"),
                    headers=headers,
                    timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                )

                # Extract correlation ID from response headers for logging
                correlation_id = (
                    resp.headers.get("x-ms-correlation-id")
                    or resp.headers.get("request-id")
                    or "N/A"
                )

                # 2xx => success
                if 200 <= resp.status_code < 300:
                    logger.info(
                        f"HTTP {resp.status_code} success on attempt {attempt + 1}. "
                        f"Correlation ID: {correlation_id}. "
                        f"Response: {self._truncate_text(resp.text, 200)}"
                    )
                    return True

                # Log non-success responses
                response_text = self._truncate_text(resp.text, 500)

                # Retry transient
                if resp.status_code in (408, 429) or 500 <= resp.status_code < 600:
                    if attempt < DEFAULT_MAX_RETRIES:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    # Final attempt failed
                    logger.error(
                        f"HTTP {resp.status_code} final failure after {DEFAULT_MAX_RETRIES + 1} attempts. "
                        f"Correlation ID: {correlation_id}. "
                        f"Response: {response_text}"
                    )
                else:
                    # Non-retryable error
                    logger.error(
                        f"HTTP {resp.status_code} non-retryable error. "
                        f"Correlation ID: {correlation_id}. "
                        f"Response: {response_text}"
                    )
                return False

            except requests.RequestException as e:
                if attempt < DEFAULT_MAX_RETRIES:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                # Final attempt failed
                logger.error(
                    f"Request failed after {DEFAULT_MAX_RETRIES + 1} attempts with exception: {e}"
                )
                return False
        return False

    # ------------- Payload mapping ------------------

    def _build_export_request(self, spans: Sequence[ReadableSpan]) -> dict[str, Any]:
        # Group by instrumentation scope (name, version)
        scope_map: dict[tuple[str, str | None], list[dict[str, Any]]] = {}

        for sp in spans:
            scope = sp.instrumentation_scope
            scope_key = (scope.name, scope.version)
            scope_map.setdefault(scope_key, []).append(self._map_span(sp))

        scope_spans: list[dict[str, Any]] = []
        for (name, version), mapped_spans in scope_map.items():
            scope_spans.append(
                {
                    "scope": {
                        "name": name,
                        "version": version,
                    },
                    "spans": mapped_spans,
                }
            )

        # Resource attributes (from the first span – all spans in a batch usually share resource)
        # If you need to merge across spans, adapt accordingly.
        resource_attrs = {}
        if spans:
            resource_attrs = dict(getattr(spans[0].resource, "attributes", {}) or {})

        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": resource_attrs or None},
                    "scopeSpans": scope_spans,
                }
            ]
        }

    def _map_span(self, sp: ReadableSpan) -> dict[str, Any]:
        ctx = sp.context

        parent_span_id = None
        if sp.parent is not None and sp.parent.span_id != 0:
            parent_span_id = hex_span_id(sp.parent.span_id)

        # attributes
        attrs = dict(sp.attributes or {})
        # events
        events = []
        for ev in sp.events:
            ev_attrs = dict(ev.attributes or {}) if ev.attributes else None
            events.append(
                {
                    "timeUnixNano": ev.timestamp,  # already ns
                    "name": ev.name,
                    "attributes": ev_attrs,
                }
            )
        if not events:
            events = None

        # links
        links = []
        for ln in sp.links or []:
            ln_attrs = dict(ln.attributes or {}) if ln.attributes else None
            links.append(
                {
                    "traceId": hex_trace_id(ln.context.trace_id),
                    "spanId": hex_span_id(ln.context.span_id),
                    "attributes": ln_attrs,
                }
            )
        if not links:
            links = None

        # status
        status_code = sp.status.status_code if sp.status else StatusCode.UNSET
        status = {
            "code": status_name(status_code),
            "message": getattr(sp.status, "description", "") or "",
        }

        # times are ns in ReadableSpan
        start_ns = sp.start_time
        end_ns = sp.end_time

        span_dict = {
            "traceId": hex_trace_id(ctx.trace_id),
            "spanId": hex_span_id(ctx.span_id),
            "parentSpanId": parent_span_id,
            "name": sp.name,
            "kind": kind_name(sp.kind),
            "startTimeUnixNano": start_ns,
            "endTimeUnixNano": end_ns,
            "attributes": attrs or None,
            "events": events,
            "links": links,
            "status": status,
        }

        # Apply truncation if needed
        return truncate_span(span_dict)

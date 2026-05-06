# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# pip install opentelemetry-sdk opentelemetry-api requests

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, final

import requests
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from .utils import (
    DEFAULT_MAX_PAYLOAD_BYTES,
    build_export_url,
    chunk_by_size,
    estimate_span_bytes,
    get_validated_domain_override,
    hex_span_id,
    hex_trace_id,
    kind_name,
    parse_retry_after,
    filter_and_partition_by_identity,
    status_name,
    truncate_span,
)

# ---- Exporter ---------------------------------------------------------------

# Hardcoded constants - not configurable
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_ENDPOINT_URL = "https://agent365.svc.cloud.microsoft"

# Create logger for this module - inherits from 'microsoft_agents_a365.observability.core'
logger = logging.getLogger(__name__)


@final
class _Agent365Exporter(SpanExporter):
    """
    Agent 365 span exporter for Agent 365:
      * Partitions spans by (tenantId, agentId)
      * Builds OTLP-like JSON: resourceSpans -> scopeSpans -> spans
      * POSTs per group to https://{endpoint}/observability/tenants/{tenantId}/otlp/agents/{agentId}/traces?api-version=1
      *   or, when use_s2s_endpoint is True, https://{endpoint}/observabilityService/tenants/{tenantId}/otlp/agents/{agentId}/traces?api-version=1
      * Adds Bearer token via token_resolver(agentId, tenantId)
    """

    def __init__(
        self,
        token_resolver: Callable[[str, str], str | None],
        cluster_category: str = "prod",
        use_s2s_endpoint: bool = False,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    ):
        if token_resolver is None:
            raise ValueError("token_resolver must be provided.")
        self._session = requests.Session()
        self._closed = False
        self._lock = threading.Lock()
        self._token_resolver = token_resolver
        self._cluster_category = cluster_category
        self._use_s2s_endpoint = use_s2s_endpoint
        self._max_payload_bytes = max_payload_bytes
        # Read domain override once at initialization
        self._domain_override = get_validated_domain_override()

    # ------------- SpanExporter API -----------------

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._closed:
            return SpanExportResult.FAILURE

        try:
            groups = filter_and_partition_by_identity(spans)
            if not groups:
                # No eligible genAI spans to export after filtering/partitioning; treat as success
                logger.info("No eligible genAI spans to export; nothing exported.")
                return SpanExportResult.SUCCESS

            # Log number of groups and total span count
            total_spans = sum(len(activities) for activities in groups.values())
            logger.debug(
                f"Found {len(groups)} identity groups with {total_spans} total spans to export"
            )

            any_failure = False
            for (tenant_id, agent_id), activities in groups.items():
                # Map and truncate spans first, then chunk by estimated byte size
                mapped_spans = self._map_and_truncate_spans(activities)
                resource_attrs = self._get_resource_attributes(activities)
                chunks = chunk_by_size(
                    mapped_spans,
                    lambda ms: estimate_span_bytes(ms[0]),
                    self._max_payload_bytes,
                )

                if len(chunks) > 1:
                    # Logged at DEBUG to avoid leaking tenant/agent IDs in production logs.
                    logger.debug(
                        f"Split {len(activities)} spans into {len(chunks)} chunks "
                        f"for tenantId: {tenant_id}, agentId: {agent_id}"
                    )

                # Resolve endpoint: domain override > default URL
                if self._domain_override:
                    endpoint = self._domain_override
                else:
                    endpoint = DEFAULT_ENDPOINT_URL

                url = build_export_url(endpoint, agent_id, tenant_id, self._use_s2s_endpoint)

                # Log endpoint details at DEBUG to avoid leaking IDs in production logs
                logger.debug(
                    f"Exporting {len(activities)} spans to endpoint: {url} "
                    f"(tenant: {tenant_id}, agent: {agent_id})"
                )

                headers = {"content-type": "application/json"}
                try:
                    token = self._token_resolver(agent_id, tenant_id)
                    if token:
                        # Warn if sending bearer token over non-HTTPS connection
                        if not url.lower().startswith("https://"):
                            logger.warning(
                                "Bearer token is being sent over a non-HTTPS connection. "
                                "This may expose credentials in transit."
                            )
                        headers["authorization"] = f"Bearer {token}"
                        logger.debug(f"Token resolved successfully for agent {agent_id}")
                    else:
                        logger.debug(f"No token returned for agent {agent_id}")
                except Exception as e:
                    # If token resolution fails, treat as failure for this group
                    logger.error(
                        f"Token resolution failed for agent {agent_id}, tenant {tenant_id}: {e}"
                    )
                    any_failure = True
                    continue

                # Send each chunk (all-or-nothing: fail group on first chunk failure)
                group_failed = False
                for i, chunk in enumerate(chunks):
                    payload = self._build_envelope(chunk, resource_attrs)
                    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                    body_bytes = len(body.encode("utf-8"))
                    logger.debug(
                        f"Sending chunk {i + 1} of {len(chunks)} "
                        f"({len(chunk)} spans, {body_bytes} bytes)"
                    )
                    # Defensive check: the estimator covers per-span content but not
                    # envelope overhead (resource attributes, scope wrappers). Warn if
                    # the assembled body exceeds the configured limit so operators can
                    # observe estimator drift before the server starts rejecting requests.
                    if body_bytes > self._max_payload_bytes:
                        logger.warning(
                            f"Chunk {i + 1} of {len(chunks)} body size ({body_bytes} bytes) "
                            f"exceeds max_payload_bytes ({self._max_payload_bytes}); "
                            "estimator may be under-counting envelope overhead. "
                            f"Tenant: {tenant_id}, agent: {agent_id}, spans: {len(chunk)}."
                        )

                    ok = self._post_with_retries(url, body, headers)
                    if not ok:
                        logger.error(
                            f"Chunk {i + 1} of {len(chunks)} failed for "
                            f"tenant {tenant_id}, agent {agent_id}"
                        )
                        any_failure = True
                        group_failed = True
                        break

                if group_failed:
                    continue

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
                    logger.debug(
                        f"HTTP {resp.status_code} success on attempt {attempt + 1}. "
                        f"Correlation ID: {correlation_id}. "
                        f"Response: {self._truncate_text(resp.text, 200)}"
                    )
                    return True

                # Log non-success responses
                response_text = self._truncate_text(resp.text, 500)

                # Retry transient
                if resp.status_code in (408, 429) or 500 <= resp.status_code < 600:
                    # Respect Retry-After header for 429 responses
                    retry_after = parse_retry_after(resp.headers)
                    if attempt < DEFAULT_MAX_RETRIES:
                        if retry_after is not None:
                            time.sleep(min(retry_after, 60.0))
                        else:
                            # Exponential backoff with base 0.5s
                            time.sleep(0.5 * (2**attempt))
                        continue
                    # Final attempt failed
                    logger.error(
                        f"HTTP {resp.status_code} final failure after "
                        f"{DEFAULT_MAX_RETRIES + 1} attempts. "
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
                    # Exponential backoff with base 0.5s
                    time.sleep(0.5 * (2**attempt))
                    continue
                # Final attempt failed
                logger.error(f"Request failed after {DEFAULT_MAX_RETRIES + 1} attempts: {e}")
                return False
        return False

    # ------------- Payload mapping ------------------

    def _map_and_truncate_spans(
        self, spans: Sequence[ReadableSpan]
    ) -> list[tuple[dict[str, Any], str, str | None]]:
        """Map ReadableSpans to OTLP dicts and apply per-span truncation.

        Returns a list of (mapped_span, scope_name, scope_version) tuples so
        that envelope grouping by instrumentation scope can be performed
        efficiently after byte-size chunking.
        """
        result: list[tuple[dict[str, Any], str, str | None]] = []
        for sp in spans:
            scope = sp.instrumentation_scope
            scope_name = scope.name if scope is not None else "unknown"
            scope_version = scope.version if scope is not None else None
            result.append((self._map_span(sp), scope_name, scope_version))
        return result

    @staticmethod
    def _get_resource_attributes(spans: Sequence[ReadableSpan]) -> dict[str, Any]:
        """Extract resource attributes from the first span in the batch."""
        if spans:
            return dict(getattr(spans[0].resource, "attributes", {}) or {})
        return {}

    def _build_envelope(
        self,
        mapped_spans: Sequence[tuple[dict[str, Any], str, str | None]],
        resource_attrs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build an OTLP export request envelope from pre-mapped spans."""
        scope_map: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
        for mapped_span, scope_name, scope_version in mapped_spans:
            scope_map.setdefault((scope_name, scope_version), []).append(mapped_span)

        scope_spans: list[dict[str, Any]] = [
            {
                "scope": {"name": name, "version": version},
                "spans": spans,
            }
            for (name, version), spans in scope_map.items()
        ]

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

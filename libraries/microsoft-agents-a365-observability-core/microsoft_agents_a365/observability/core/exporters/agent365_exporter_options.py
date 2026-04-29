# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Awaitable, Callable, Optional

from .utils import DEFAULT_MAX_PAYLOAD_BYTES


class Agent365ExporterOptions:
    """
    Configuration for Agent365Exporter.
    Only cluster_category and token_resolver are required for core operation.
    """

    def __init__(
        self,
        cluster_category: str = "prod",
        token_resolver: Optional[Callable[[str, str], Awaitable[Optional[str]]]] = None,
        use_s2s_endpoint: bool = False,
        max_queue_size: int = 2048,
        scheduled_delay_ms: int = 5000,
        exporter_timeout_ms: int = 30000,
        max_export_batch_size: int = 512,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    ):
        """
        Args:
            cluster_category: Cluster region argument. Defaults to 'prod'.
            token_resolver: Async callable that resolves the auth token (REQUIRED).
            use_s2s_endpoint: Use the S2S endpoint instead of standard endpoint.
            max_queue_size: Maximum queue size for the batch processor. Default is 2048.
            scheduled_delay_ms: Delay between export batches (ms). Default is 5000.
            exporter_timeout_ms: Timeout for the export operation (ms). Default is 30000.
            max_export_batch_size: Maximum batch size for export operations. Default is 512.
            max_payload_bytes: Upper bound on HTTP request body size in bytes. The exporter
                splits per-identity batches into sub-batches whose estimated size stays under
                this limit, providing headroom under the A365 1 MB server limit. Default is
                900_000 (~100 KB headroom for estimator error and JSON envelope overhead).
        """
        self.cluster_category = cluster_category
        self.token_resolver = token_resolver
        self.use_s2s_endpoint = use_s2s_endpoint
        self.max_queue_size = max_queue_size
        self.scheduled_delay_ms = scheduled_delay_ms
        self.exporter_timeout_ms = exporter_timeout_ms
        self.max_export_batch_size = max_export_batch_size
        self.max_payload_bytes = max_payload_bytes

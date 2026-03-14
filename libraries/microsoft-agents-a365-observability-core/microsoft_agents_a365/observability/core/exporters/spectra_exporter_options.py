# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal


class SpectraExporterOptions:
    """
    Configuration for exporting traces to a Spectra Collector sidecar via OTLP.

    Spectra Collector is deployed as a Kubernetes sidecar that accepts
    standard OTLP telemetry on localhost. Defaults are tuned for this
    deployment topology — most consumers should not need to override them.

    Note: Batch processor fields (max_queue_size, scheduled_delay_ms, etc.)
    are duplicated from Agent365ExporterOptions intentionally — these two
    options classes have no shared base class per design decision C4.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        protocol: Literal["grpc", "http"] = "grpc",
        insecure: bool = True,
        max_queue_size: int = 2048,
        scheduled_delay_ms: int = 5000,
        exporter_timeout_ms: int = 30000,
        max_export_batch_size: int = 512,
    ):
        """
        Args:
            endpoint: Spectra sidecar OTLP endpoint. Default: http://localhost:4317.
            protocol: OTLP protocol — "grpc" or "http". Default: grpc.
            insecure: Use insecure (no TLS) connection. Default: True (localhost sidecar).
            max_queue_size: Batch processor queue size. Default: 2048.
            scheduled_delay_ms: Export interval in milliseconds. Default: 5000.
            exporter_timeout_ms: Export timeout in milliseconds. Default: 30000.
            max_export_batch_size: Max spans per export batch. Default: 512.
        """
        if protocol not in ("grpc", "http"):
            raise ValueError(f"protocol must be 'grpc' or 'http', got '{protocol}'")
        self.endpoint = endpoint
        self.protocol = protocol
        self.insecure = insecure
        self.max_queue_size = max_queue_size
        self.scheduled_delay_ms = scheduled_delay_ms
        self.exporter_timeout_ms = exporter_timeout_ms
        self.max_export_batch_size = max_export_batch_size

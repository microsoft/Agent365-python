# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass

from .inference_operation_type import InferenceOperationType


@dataclass
class ServiceEndpoint:
    """Represents a service endpoint with hostname and optional port."""

    hostname: str
    """The hostname of the service endpoint."""

    port: int | None = None
    """The port of the service endpoint."""


@dataclass
class InferenceCallDetails:
    """Details of an inference call for generative AI operations."""

    operationName: InferenceOperationType
    model: str
    providerName: str
    inputTokens: int | None = None
    outputTokens: int | None = None
    finishReasons: list[str] | None = None
    thoughtProcess: str | None = None
    endpoint: ServiceEndpoint | None = None

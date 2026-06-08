# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass

from .inference_operation_type import InferenceOperationType
from .models.service_endpoint import ServiceEndpoint


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

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass

from .inference_operation_type import InferenceOperationType
from .models.service_endpoint import ServiceEndpoint


@dataclass
class InferenceCallDetails:
    """Details of an inference call for generative AI operations."""

    operationName: InferenceOperationType
    model: str | None
    providerName: str
    responseModel: str | None = None
    inputTokens: int | None = None
    outputTokens: int | None = None
    cacheReadInputTokens: int | None = None
    cacheWriteInputTokens: int | None = None
    finishReasons: list[str] | None = None
    thoughtProcess: str | None = None
    endpoint: ServiceEndpoint | None = None

    def __post_init__(self) -> None:
        """Validate required model identity."""
        if not (self.model and self.model.strip()) and not (
            self.responseModel and self.responseModel.strip()
        ):
            raise ValueError("At least one of model or responseModel must be provided")

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
    inputTokens: int | None = None
    outputTokens: int | None = None
    finishReasons: list[str] | None = None
    thoughtProcess: str | None = None
    endpoint: ServiceEndpoint | None = None
    # NOTE: Appended after all pre-existing fields (rather than inserted in the
    # middle) to preserve positional-argument compatibility for existing callers.
    responseModel: str | None = None
    cacheReadInputTokens: int | None = None
    cacheWriteInputTokens: int | None = None

    def __post_init__(self) -> None:
        """Normalize and validate required model identity.

        Whitespace-only `model`/`responseModel` values are normalized to
        `None` so that validation and downstream consumers (e.g.
        `InferenceScope`) never treat a blank string as a present model.
        """
        if self.model is not None:
            self.model = self.model.strip() or None
        if self.responseModel is not None:
            self.responseModel = self.responseModel.strip() or None

        if not self.model and not self.responseModel:
            raise ValueError("At least one of model or responseModel must be provided")

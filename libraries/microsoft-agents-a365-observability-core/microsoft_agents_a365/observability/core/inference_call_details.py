# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass

from .inference_operation_type import InferenceOperationType


@dataclass
class InferenceCallDetails:
    """Details of an inference call for generative AI operations."""

    operationName: InferenceOperationType
    model: str
    providerName: str
    inputTokens: int | None = None
    outputTokens: int | None = None
    finishReasons: list[str] | None = None
    responseId: str | None = None

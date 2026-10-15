# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class InferenceOperationType(Enum):
    """Supported inference operation types for generative AI."""

    CHAT = "Chat"
    TEXT_COMPLETION = "TextCompletion"
    GENERATE_CONTENT = "GenerateContent"

    @property
    def canonical_name(self) -> str:
        """The canonical lowercase operation name per the OpenTelemetry GenAI
        semantic conventions (e.g. ``chat``, ``text_completion``,
        ``generate_content``). Used for both the span name prefix and the
        ``gen_ai.operation.name`` attribute.
        """
        return self.name.lower()

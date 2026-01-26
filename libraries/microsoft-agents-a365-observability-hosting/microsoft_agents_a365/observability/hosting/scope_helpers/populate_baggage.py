# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder

from .utils import (
    get_caller_pairs,
    get_conversation_pairs,
    get_execution_type_pair,
    get_source_metadata_pairs,
    get_target_agent_pairs,
    get_tenant_id_pair,
)


def _iter_all_pairs(turn_context: TurnContext) -> Iterator[tuple[str, Any]]:
    activity = turn_context.activity
    if not activity:
        return
    yield from get_caller_pairs(activity)
    yield from get_execution_type_pair(activity)
    yield from get_target_agent_pairs(activity)
    yield from get_tenant_id_pair(activity)
    yield from get_source_metadata_pairs(activity)
    yield from get_conversation_pairs(activity)


def populate(builder: BaggageBuilder, turn_context: TurnContext) -> BaggageBuilder:
    """Populate BaggageBuilder with baggage values extracted from a turn context.

    Args:
        builder: The BaggageBuilder instance to populate
        turn_context: The TurnContext containing activity information

    Returns:
        The updated BaggageBuilder instance (for method chaining)
    """
    builder.set_pairs(_iter_all_pairs(turn_context))
    return builder

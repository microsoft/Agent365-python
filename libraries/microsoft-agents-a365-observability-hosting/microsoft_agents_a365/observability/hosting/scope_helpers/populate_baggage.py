from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from microsoft_agents.hosting.core.turn_context import TurnContext

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


def from_turn_context(turn_context: TurnContext) -> dict:
    """Populate builder with baggage values extracted from a turn context."""
    return dict(_iter_all_pairs(turn_context))

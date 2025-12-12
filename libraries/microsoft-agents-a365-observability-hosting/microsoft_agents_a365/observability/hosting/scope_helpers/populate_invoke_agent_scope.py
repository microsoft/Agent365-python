from __future__ import annotations

from typing import TYPE_CHECKING

from microsoft_agents_a365.observability.core.invoke_agent_scope import InvokeAgentScope

from .utils import (
    get_caller_pairs,
    get_conversation_pairs,
    get_execution_type_pair,
    get_source_metadata_pairs,
    get_target_agent_pairs,
    get_tenant_id_pair,
)

if TYPE_CHECKING:
    from microsoft_agents.hosting.core.turn_context import TurnContext


def populate_invoke_agent_scope_from_turn_context(
    scope: InvokeAgentScope, turn_context: TurnContext
) -> InvokeAgentScope:
    """
    Populate all supported InvokeAgentScope tags from the provided TurnContext.
    :param scope: The InvokeAgentScope instance to populate.
    :param turn_context: The TurnContext containing activity information.
    :return: The updated InvokeAgentScope instance.
    """
    if not turn_context:
        raise ValueError("turn_context is required")

    if not turn_context.activity:
        return scope

    activity = turn_context.activity

    set_caller_tags(scope, activity)
    set_execution_type_tags(scope, activity)
    set_target_agent_tags(scope, activity)
    set_tenant_id_tags(scope, activity)
    set_source_metadata_tags(scope, activity)
    set_conversation_id_tags(scope, activity)
    set_input_message_tags(scope, activity)
    return scope


def set_caller_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the caller-related attribute values from the Activity."""
    scope.record_attributes(get_caller_pairs(activity))


def set_execution_type_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the execution type tag based on caller and recipient agentic status."""
    scope.record_attributes(get_execution_type_pair(activity))


def set_target_agent_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the target agent-related tags from the Activity."""
    scope.record_attributes(get_target_agent_pairs(activity))


def set_tenant_id_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the tenant ID tag, extracting from ChannelData if necessary."""
    scope.record_attributes(get_tenant_id_pair(activity))


def set_source_metadata_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the source metadata tags from the Activity."""
    scope.record_attributes(get_source_metadata_pairs(activity))


def set_conversation_id_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the conversation ID and item link tags from the Activity."""
    scope.record_attributes(get_conversation_pairs(activity))


def set_input_message_tags(scope: InvokeAgentScope, activity) -> None:
    """Sets the input message tag from the Activity."""
    if activity.text:
        scope.record_input_messages([activity.text])

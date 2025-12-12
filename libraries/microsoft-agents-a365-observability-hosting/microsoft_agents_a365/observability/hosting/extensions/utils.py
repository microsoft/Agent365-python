# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from collections.abc import Iterator
from typing import Any

from microsoft_agents.activity import Activity
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_AGENT_UPN_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CALLER_NAME_KEY,
    GEN_AI_CALLER_TENANT_ID_KEY,
    GEN_AI_CALLER_UPN_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_CONVERSATION_ITEM_LINK_KEY,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.execution_type import ExecutionType

AGENT_ROLE = "agenticUser"


def _is_agentic(entity: Any) -> bool:
    if not entity:
        return False
    return bool(
        entity.agentic_user_id
        or ((role := entity.role) and isinstance(role, str) and role.lower() == AGENT_ROLE.lower())
    )


def get_caller_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    frm = activity.from_property
    if not frm:
        return
    yield GEN_AI_CALLER_ID_KEY, frm.aad_object_id
    yield GEN_AI_CALLER_NAME_KEY, frm.name
    yield GEN_AI_CALLER_UPN_KEY, frm.agentic_user_id
    yield GEN_AI_CALLER_TENANT_ID_KEY, frm.tenant_id


def get_execution_type_pair(activity: Activity) -> Iterator[tuple[str, Any]]:
    frm = activity.from_property
    rec = activity.recipient
    is_agentic_caller = _is_agentic(frm)
    is_agentic_recipient = _is_agentic(rec)
    exec_type = (
        ExecutionType.AGENT_TO_AGENT.value
        if (is_agentic_caller and is_agentic_recipient)
        else ExecutionType.HUMAN_TO_AGENT.value
    )
    yield GEN_AI_EXECUTION_TYPE_KEY, exec_type


def get_target_agent_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    rec = activity.recipient
    if not rec:
        return
    yield GEN_AI_AGENT_ID_KEY, rec.agentic_app_id
    yield GEN_AI_AGENT_NAME_KEY, rec.name
    yield GEN_AI_AGENT_AUID_KEY, rec.aad_object_id
    yield GEN_AI_AGENT_UPN_KEY, rec.agentic_user_id
    yield (
        GEN_AI_AGENT_DESCRIPTION_KEY,
        rec.role,
    )


def get_tenant_id_pair(activity: Activity) -> Iterator[tuple[str, Any]]:
    yield TENANT_ID_KEY, activity.recipient.tenant_id


def get_source_metadata_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    """
    Generate source metadata pairs from activity, handling both string and ChannelId object cases.

    :param activity: The activity object (Activity instance or dict)
    :return: Iterator of (key, value) tuples for source metadata
    """
    # Handle channel_id (can be string or ChannelId object)
    channel_id = activity.channel_id

    # Extract channel name from either string or ChannelId object
    channel_name = None
    sub_channel = None

    if channel_id is not None:
        if isinstance(channel_id, str):
            # Direct string value
            channel_name = channel_id
        elif hasattr(channel_id, "channel"):
            # ChannelId object
            channel_name = channel_id.channel
            sub_channel = channel_id.sub_channel

    # Yield channel name as source name
    yield GEN_AI_EXECUTION_SOURCE_NAME_KEY, channel_name
    yield GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY, sub_channel


def get_conversation_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    conv = activity.conversation
    conversation_id = conv.id if conv else None

    item_link = activity.service_url

    yield GEN_AI_CONVERSATION_ID_KEY, conversation_id
    yield GEN_AI_CONVERSATION_ITEM_LINK_KEY, item_link

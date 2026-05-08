# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
from collections.abc import Iterator
from typing import Any

from microsoft_agents.activity import Activity
from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_EMAIL_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_CONVERSATION_ITEM_LINK_KEY,
    TENANT_ID_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)

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
    yield USER_ID_KEY, frm.aad_object_id or frm.agentic_user_id or frm.id
    yield USER_NAME_KEY, frm.name
    yield USER_EMAIL_KEY, frm.agentic_user_id


def get_target_agent_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    rec = activity.recipient
    if not rec:
        return
    yield GEN_AI_AGENT_ID_KEY, activity.get_agentic_instance_id()
    yield GEN_AI_AGENT_NAME_KEY, rec.name
    yield GEN_AI_AGENT_AUID_KEY, rec.aad_object_id
    yield GEN_AI_AGENT_EMAIL_KEY, activity.get_agentic_user()
    yield (
        GEN_AI_AGENT_DESCRIPTION_KEY,
        rec.role,
    )


def get_tenant_id_pair(activity: Activity) -> Iterator[tuple[str, Any]]:
    yield TENANT_ID_KEY, activity.recipient.tenant_id


def get_channel_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    """
    Generate channel pairs from activity, handling both string and ChannelId object cases.

    :param activity: The activity object (Activity instance or dict)
    :return: Iterator of (key, value) tuples for channel information
    """
    # Handle channel_id (can be string or ChannelId object)
    channel_id = activity.channel_id

    # Extract channel name from either string or ChannelId object
    channel_name = None
    sub_channel = None

    if channel_id is not None:
        # Check for ChannelId object first
        if hasattr(channel_id, "channel"):
            # ChannelId object
            channel_name = channel_id.channel
            sub_channel = channel_id.sub_channel
        elif isinstance(channel_id, str):
            # Direct string value
            channel_name = channel_id

    # Try to get sub_channel from productContext in channel_data if sub_channel is not set
    if not sub_channel and activity.channel_data:
        try:
            # Convert channel_data to dict if it's a string
            if isinstance(activity.channel_data, str):
                channel_data_dict = json.loads(activity.channel_data)
            elif isinstance(activity.channel_data, dict):
                channel_data_dict = activity.channel_data
            else:
                # Try to convert to dict if it has __dict__
                channel_data_dict = getattr(activity.channel_data, "__dict__", {})

            # Extract productContext if available
            if isinstance(channel_data_dict, dict) and "productContext" in channel_data_dict:
                product_context = channel_data_dict["productContext"]
                if isinstance(product_context, str):
                    sub_channel = product_context
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Silently ignore any parsing errors
            pass

    # Yield channel name as source name
    yield CHANNEL_NAME_KEY, channel_name
    yield CHANNEL_LINK_KEY, sub_channel


def get_conversation_pairs(activity: Activity) -> Iterator[tuple[str, Any]]:
    conv = activity.conversation
    conversation_id = conv.id if conv else None

    item_link = activity.service_url

    yield GEN_AI_CONVERSATION_ID_KEY, conversation_id
    yield GEN_AI_CONVERSATION_ITEM_LINK_KEY, item_link

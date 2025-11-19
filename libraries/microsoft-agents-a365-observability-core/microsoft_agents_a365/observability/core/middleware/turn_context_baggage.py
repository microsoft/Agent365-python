from __future__ import annotations

import json
from typing import Any, Iterator, Mapping

from ..constants import (
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_AGENT_UPN_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CALLER_NAME_KEY,
    GEN_AI_CALLER_TENANT_ID_KEY,
    GEN_AI_CALLER_UPN_KEY,
    GEN_AI_CALLER_USER_ID_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_CONVERSATION_ITEM_LINK_KEY,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    TENANT_ID_KEY,
)
from ..execution_type import ExecutionType

AGENT_ROLE = "agenticUser"
CHANNEL_ID_AGENTS = "agents"


def _safe_get(obj: Any, *names: str) -> Any:
    """Attempt multiple attribute/dict keys; return first non-None."""
    for n in names:
        if obj is None:
            continue
        # dict-like
        if isinstance(obj, Mapping) and n in obj:
            return obj[n]
        # attribute-like (support both camelCase and snake_case lookups)
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def _extract_channel_data(activity: Any) -> Mapping[str, Any] | None:
    cd = _safe_get(activity, "channel_data")
    if cd is None:
        return None
    if isinstance(cd, Mapping):
        return cd
    if isinstance(cd, str):
        try:
            return json.loads(cd)
        except Exception:
            return None
    return None


def _iter_caller_pairs(activity: Any) -> Iterator[tuple[str, Any]]:
    frm = _safe_get(activity, "from")
    if not frm:
        return
    yield GEN_AI_CALLER_ID_KEY, _safe_get(frm, "id")
    name = _safe_get(frm, "name")
    yield GEN_AI_CALLER_NAME_KEY, name
    # Reuse 'name' as UPN if no separate field
    upn = _safe_get(frm, "upn") or name
    yield GEN_AI_CALLER_UPN_KEY, upn
    user_id = _safe_get(frm, "agentic_user_id", "aad_object_id")
    yield GEN_AI_CALLER_USER_ID_KEY, user_id
    tenant_id = _safe_get(frm, "tenant_id")
    yield GEN_AI_CALLER_TENANT_ID_KEY, tenant_id


def _is_agentic(entity: Any) -> bool:
    return bool(
        _safe_get(
            entity,
            "agentic_user_id",
        )
        or (
            (role := _safe_get(entity, "role", "Role"))
            and isinstance(role, str)
            and role.lower() == AGENT_ROLE.lower()
        )
    )


def _iter_execution_type_pair(activity: Any) -> Iterator[tuple[str, Any]]:
    frm = _safe_get(activity, "from")
    rec = _safe_get(activity, "recipient")
    is_agentic_caller = _is_agentic(frm)
    is_agentic_recipient = _is_agentic(rec)
    exec_type = (
        ExecutionType.AGENT_TO_AGENT.value
        if (is_agentic_caller and is_agentic_recipient)
        else ExecutionType.HUMAN_TO_AGENT.value
    )
    yield GEN_AI_EXECUTION_TYPE_KEY, exec_type


def _iter_target_agent_pairs(activity: Any) -> Iterator[tuple[str, Any]]:
    rec = _safe_get(activity, "recipient")
    if not rec:
        return
    yield GEN_AI_AGENT_ID_KEY, _safe_get(rec, "agentic_app_id")
    yield GEN_AI_AGENT_NAME_KEY, _safe_get(rec, "name")
    auid = _safe_get(rec, "agentic_user_id", "aad_object_id")
    yield GEN_AI_AGENT_AUID_KEY, auid
    yield GEN_AI_AGENT_UPN_KEY, _safe_get(rec, "upn", "name")
    yield (
        GEN_AI_AGENT_DESCRIPTION_KEY,
        _safe_get(rec, "role"),
    )


def _iter_tenant_id_pair(activity: Any) -> Iterator[tuple[str, Any]]:
    rec = _safe_get(activity, "recipient")
    tenant_id = _safe_get(rec, "tenant_id")
    if not tenant_id:
        cd_dict = _extract_channel_data(activity)
        # channelData.tenant.id
        try:
            tenant_id = (
                cd_dict
                and isinstance(cd_dict.get("tenant"), Mapping)
                and cd_dict["tenant"].get("id")
            )
        except Exception:
            tenant_id = None
    yield TENANT_ID_KEY, tenant_id


def _iter_source_metadata_pairs(activity: Any) -> Iterator[tuple[str, Any]]:
    """
    Generate source metadata pairs from activity, handling both string and ChannelId object cases.

    :param activity: The activity object (Activity instance or dict)
    :return: Iterator of (key, value) tuples for source metadata
    """
    # Handle channel_id (can be string or ChannelId object)
    channel_id = _safe_get(activity, "channel_id")

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
            sub_channel = getattr(channel_id, "sub_channel", None)
        elif isinstance(channel_id, dict):
            # Serialized ChannelId as dict
            channel_name = channel_id.get("channel")
            sub_channel = channel_id.get("sub_channel")

    # Yield channel name as source name
    yield GEN_AI_EXECUTION_SOURCE_NAME_KEY, channel_name
    yield GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY, sub_channel


def _iter_conversation_pairs(activity: Any) -> Iterator[tuple[str, Any]]:
    conv = _safe_get(activity, "conversation")
    conversation_id = _safe_get(conv, "id")

    item_link = _safe_get(activity, "service_url")

    yield GEN_AI_CONVERSATION_ID_KEY, conversation_id
    yield GEN_AI_CONVERSATION_ITEM_LINK_KEY, item_link


def _iter_all_pairs(turn_context: Any) -> Iterator[tuple[str, Any]]:
    activity = _safe_get(
        turn_context,
        "activity",
    )
    if not activity:
        return
    yield from _iter_caller_pairs(activity)
    yield from _iter_execution_type_pair(activity)
    yield from _iter_target_agent_pairs(activity)
    yield from _iter_tenant_id_pair(activity)
    yield from _iter_source_metadata_pairs(activity)
    yield from _iter_conversation_pairs(activity)


def from_turn_context(turn_context: Any) -> dict:
    """Populate builder with baggage values extracted from a turn context."""
    return dict(_iter_all_pairs(turn_context))

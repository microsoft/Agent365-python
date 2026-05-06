# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from microsoft_agents.activity import Activity, ChannelAccount, ConversationAccount
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
from microsoft_agents_a365.observability.hosting.scope_helpers.utils import (
    get_caller_pairs,
    get_channel_pairs,
    get_conversation_pairs,
    get_target_agent_pairs,
    get_tenant_id_pair,
)


def test_get_caller_pairs():
    """Test get_caller_pairs extracts caller information from activity."""
    from_account = ChannelAccount(
        aad_object_id="caller-aad-id",
        name="Test Caller",
        agentic_user_id="caller-upn",
        tenant_id="caller-tenant-id",
    )
    activity = Activity(type="message", from_property=from_account)

    result = list(get_caller_pairs(activity))

    assert (USER_ID_KEY, "caller-aad-id") in result
    assert (USER_NAME_KEY, "Test Caller") in result
    assert (USER_EMAIL_KEY, "caller-upn") in result


def test_get_target_agent_pairs():
    """Test get_target_agent_pairs extracts target agent information."""
    recipient = ChannelAccount(
        agentic_app_id="agent-app-id",
        name="Test Agent",
        aad_object_id="agent-auid",
        agentic_user_id="agent-upn",
        role="agenticAppInstance",
    )
    activity = Activity(type="message", recipient=recipient)

    result = list(get_target_agent_pairs(activity))

    assert (GEN_AI_AGENT_ID_KEY, "agent-app-id") in result
    assert (GEN_AI_AGENT_NAME_KEY, "Test Agent") in result
    assert (GEN_AI_AGENT_AUID_KEY, "agent-auid") in result
    assert (GEN_AI_AGENT_EMAIL_KEY, "agent-upn") in result
    assert (GEN_AI_AGENT_DESCRIPTION_KEY, "agenticAppInstance") in result


def test_get_tenant_id_pair():
    """Test get_tenant_id_pair extracts tenant ID from recipient."""
    recipient = ChannelAccount(tenant_id="test-tenant-id")
    activity = Activity(type="message", recipient=recipient)

    result = list(get_tenant_id_pair(activity))

    assert (TENANT_ID_KEY, "test-tenant-id") in result


def test_get_channel_pairs():
    """Test get_channel_pairs extracts channel metadata."""
    activity = Activity(type="message", channel_id="test-channel")

    result = list(get_channel_pairs(activity))

    assert (CHANNEL_NAME_KEY, "test-channel") in result
    assert (CHANNEL_LINK_KEY, None) in result


def test_get_caller_pairs_non_teams_fallback_to_from_id():
    """Test userId falls back to from.id when aad_object_id is None (non-Teams channel)."""
    from_account = ChannelAccount(
        id="from-id-123",
        name="Non-Teams User",
    )
    activity = Activity(type="message", from_property=from_account)

    result = list(get_caller_pairs(activity))

    assert (USER_ID_KEY, "from-id-123") in result
    assert (USER_NAME_KEY, "Non-Teams User") in result
    assert (USER_EMAIL_KEY, None) in result


def test_get_caller_pairs_a2a_fallback_to_agentic_user_id():
    """Test userId falls back to agentic_user_id for A2A calls (no aad_object_id)."""
    from_account = ChannelAccount(
        id="from-id-456",
        name="Agent Caller",
        agentic_user_id="a2a-agent-guid",
    )
    activity = Activity(type="message", from_property=from_account)

    result = list(get_caller_pairs(activity))

    assert (USER_ID_KEY, "a2a-agent-guid") in result
    assert (USER_EMAIL_KEY, "a2a-agent-guid") in result


def test_get_caller_pairs_aad_object_id_wins_when_all_set():
    """Test aad_object_id takes precedence when all identifiers are present."""
    from_account = ChannelAccount(
        id="from-id-789",
        aad_object_id="aad-wins",
        name="Full User",
        agentic_user_id="agent-upn",
    )
    activity = Activity(type="message", from_property=from_account)

    result = list(get_caller_pairs(activity))

    assert (USER_ID_KEY, "aad-wins") in result
    assert (USER_NAME_KEY, "Full User") in result
    assert (USER_EMAIL_KEY, "agent-upn") in result


def test_get_caller_pairs_a2a_guid_agentic_user_id():
    """Test userId resolves to GUID AgenticUserId in A2A scenario."""
    from_account = ChannelAccount(
        id="29:1sH5NArUwkWAX",
        name="Agent Caller",
        agentic_user_id="bef730f4-d6f5-4ffb-b759-26ffa449ed7e",
    )
    activity = Activity(type="message", from_property=from_account)
    result = list(get_caller_pairs(activity))
    assert (USER_ID_KEY, "bef730f4-d6f5-4ffb-b759-26ffa449ed7e") in result


def test_get_conversation_pairs():
    """Test get_conversation_pairs extracts conversation information."""
    conversation = ConversationAccount(id="conversation-123")
    activity = Activity(
        type="message", conversation=conversation, service_url="https://example.com"
    )

    result = list(get_conversation_pairs(activity))

    assert (GEN_AI_CONVERSATION_ID_KEY, "conversation-123") in result
    assert (GEN_AI_CONVERSATION_ITEM_LINK_KEY, "https://example.com") in result

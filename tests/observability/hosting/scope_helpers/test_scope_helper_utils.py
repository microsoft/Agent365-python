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


def test_get_conversation_pairs():
    """Test get_conversation_pairs extracts conversation information."""
    conversation = ConversationAccount(id="conversation-123")
    activity = Activity(
        type="message", conversation=conversation, service_url="https://example.com"
    )

    result = list(get_conversation_pairs(activity))

    assert (GEN_AI_CONVERSATION_ID_KEY, "conversation-123") in result
    assert (GEN_AI_CONVERSATION_ITEM_LINK_KEY, "https://example.com") in result

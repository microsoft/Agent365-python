# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import MagicMock

from microsoft_agents.activity import Activity, ChannelAccount, ConversationAccount
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.observability.core.constants import GEN_AI_CALLER_ID_KEY
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
from microsoft_agents_a365.observability.hosting.scope_helpers.populate_baggage import populate


def test_populate():
    """Test populate populates BaggageBuilder from turn context."""
    # Create a real activity and turn context
    activity = Activity(
        type="message",
        from_property=ChannelAccount(
            aad_object_id="caller-id",
            name="Caller",
            agentic_user_id="caller-upn",
            tenant_id="tenant-id",
        ),
        recipient=ChannelAccount(tenant_id="tenant-id", role="user"),
        conversation=ConversationAccount(id="conv-id"),
        service_url="https://example.com",
        channel_id="test-channel",
    )
    adapter = MagicMock()
    turn_context = TurnContext(adapter, activity)

    builder = BaggageBuilder()

    result = populate(builder, turn_context)

    assert result == builder
    # Verify builder was populated by checking its internal _pairs dict
    assert len(builder._pairs) > 0
    # Verify specific expected baggage keys were set
    assert GEN_AI_CALLER_ID_KEY in builder._pairs
    assert builder._pairs[GEN_AI_CALLER_ID_KEY] == "caller-id"

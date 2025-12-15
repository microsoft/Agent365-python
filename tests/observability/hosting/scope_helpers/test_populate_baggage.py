# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import MagicMock

from microsoft_agents_a365.observability.core.constants import GEN_AI_CALLER_ID_KEY
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder
from microsoft_agents_a365.observability.hosting.scope_helpers.populate_baggage import populate


def test_populate():
    """Test populate populates BaggageBuilder from turn context."""
    # Create a mock turn context with activity
    turn_context = MagicMock()
    activity = MagicMock()
    activity.from_property = MagicMock(
        aad_object_id="caller-id",
        name="Caller",
        agentic_user_id="caller-upn",
        tenant_id="tenant-id",
    )
    activity.recipient = MagicMock(tenant_id="tenant-id", role="user")
    activity.conversation = MagicMock(id="conv-id")
    activity.service_url = "https://example.com"
    activity.channel_id = "test-channel"
    turn_context.activity = activity

    builder = BaggageBuilder()

    result = populate(builder, turn_context)

    assert result == builder
    # Verify builder was populated by checking its internal _pairs dict
    assert len(builder._pairs) > 0
    # Verify specific expected baggage keys were set
    assert GEN_AI_CALLER_ID_KEY in builder._pairs
    assert builder._pairs[GEN_AI_CALLER_ID_KEY] == "caller-id"

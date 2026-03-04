# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import MagicMock

import pytest
from microsoft_agents.activity import (
    Activity,
    ActivityEventNames,
    ActivityTypes,
    ChannelAccount,
    ConversationAccount,
)
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_CALLER_ID_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.hosting.middleware.baggage_middleware import (
    BaggageMiddleware,
)
from opentelemetry import baggage


def _make_turn_context(
    activity_type: str = "message",
    activity_name: str | None = None,
    text: str = "Hello",
) -> TurnContext:
    """Create a TurnContext with a test activity."""
    kwargs: dict = {
        "type": activity_type,
        "text": text,
        "from_property": ChannelAccount(
            aad_object_id="caller-id",
            name="Caller",
            agentic_user_id="caller-upn",
            tenant_id="tenant-id",
        ),
        "recipient": ChannelAccount(
            tenant_id="tenant-123",
            role="user",
            name="Agent",
        ),
        "conversation": ConversationAccount(id="conv-id"),
        "service_url": "https://example.com",
        "channel_id": "test-channel",
    }
    if activity_name is not None:
        kwargs["name"] = activity_name
    activity = Activity(**kwargs)
    adapter = MagicMock()
    return TurnContext(adapter, activity)


@pytest.mark.asyncio
async def test_baggage_middleware_propagates_baggage():
    """BaggageMiddleware should set baggage context for the downstream logic."""
    middleware = BaggageMiddleware()
    ctx = _make_turn_context()

    captured_caller_id = None
    captured_tenant_id = None

    async def logic():
        nonlocal captured_caller_id, captured_tenant_id
        captured_caller_id = baggage.get_baggage(GEN_AI_CALLER_ID_KEY)
        captured_tenant_id = baggage.get_baggage(TENANT_ID_KEY)

    await middleware.on_turn(ctx, logic)

    assert captured_caller_id == "caller-id"
    assert captured_tenant_id == "tenant-123"


@pytest.mark.asyncio
async def test_baggage_middleware_skips_async_reply():
    """BaggageMiddleware should skip baggage setup for ContinueConversation events."""
    middleware = BaggageMiddleware()
    ctx = _make_turn_context(
        activity_type=ActivityTypes.event,
        activity_name=ActivityEventNames.continue_conversation,
    )

    logic_called = False
    captured_caller_id = None

    async def logic():
        nonlocal logic_called, captured_caller_id
        logic_called = True
        captured_caller_id = baggage.get_baggage(GEN_AI_CALLER_ID_KEY)

    await middleware.on_turn(ctx, logic)

    assert logic_called is True
    # Baggage should NOT be set because the middleware skipped it
    assert captured_caller_id is None

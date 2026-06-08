# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from unittest.mock import MagicMock

import pytest
from microsoft_agents.activity import (
    Activity,
    ActivityEventNames,
    ActivityTypes,
    ChannelAccount,
    ChannelId,
    ConversationAccount,
)
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    TENANT_ID_KEY,
    USER_ID_KEY,
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


def _make_channel_data_turn_context(
    channel_id: ChannelId | str = "msteams",
    channel_data: object | None = None,
) -> TurnContext:
    """Create a TurnContext with channel_data for testing."""
    activity = Activity(
        type="message",
        text="Hello",
        from_property=ChannelAccount(
            aad_object_id="caller-id",
            name="Caller",
        ),
        recipient=ChannelAccount(
            tenant_id="tenant-123",
            name="Agent",
        ),
        conversation=ConversationAccount(id="conv-id"),
        service_url="https://example.com",
        channel_id=channel_id,
        channel_data=channel_data,
    )
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
        captured_caller_id = baggage.get_baggage(USER_ID_KEY)
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
        captured_caller_id = baggage.get_baggage(USER_ID_KEY)

    await middleware.on_turn(ctx, logic)

    assert logic_called is True
    # Baggage should NOT be set because the middleware skipped it
    assert captured_caller_id is None


@pytest.mark.asyncio
async def test_baggage_middleware_extracts_product_context_from_channel_data():
    """BaggageMiddleware should extract productContext from channel_data when sub_channel is not set."""

    middleware = BaggageMiddleware()
    ctx = _make_channel_data_turn_context(
        channel_id=ChannelId(channel="msteams"),  # No sub_channel
        channel_data={"productContext": "COPILOT"},
    )

    captured_channel_link = None

    async def logic():
        nonlocal captured_channel_link
        captured_channel_link = baggage.get_baggage(CHANNEL_LINK_KEY)

    await middleware.on_turn(ctx, logic)

    assert captured_channel_link == "COPILOT"


@pytest.mark.asyncio
async def test_baggage_middleware_sub_channel_takes_precedence_over_product_context():
    """BaggageMiddleware should use sub_channel when both sub_channel and productContext are present."""

    middleware = BaggageMiddleware()
    ctx = _make_channel_data_turn_context(
        channel_id=ChannelId(channel="msteams", sub_channel="teams-subchannel"),
        channel_data={"productContext": "COPILOT"},  # Should be ignored
    )

    captured_channel_link = None

    async def logic():
        nonlocal captured_channel_link
        captured_channel_link = baggage.get_baggage(CHANNEL_LINK_KEY)

    await middleware.on_turn(ctx, logic)

    # sub_channel should take precedence, productContext should be ignored
    assert captured_channel_link == "teams-subchannel"


@pytest.mark.asyncio
async def test_baggage_middleware_extracts_product_context_from_json_string_channel_data():
    """BaggageMiddleware should extract productContext from channel_data when it's a JSON string."""

    middleware = BaggageMiddleware()
    ctx = _make_channel_data_turn_context(
        channel_id=ChannelId(channel="msteams"),  # No sub_channel
        channel_data=json.dumps({"productContext": "COPILOT"}),  # JSON string
    )

    captured_channel_link = None

    async def logic():
        nonlocal captured_channel_link
        captured_channel_link = baggage.get_baggage(CHANNEL_LINK_KEY)

    await middleware.on_turn(ctx, logic)

    assert captured_channel_link == "COPILOT"


@pytest.mark.asyncio
async def test_baggage_middleware_handles_invalid_json_channel_data_gracefully():
    """BaggageMiddleware should handle invalid JSON in channel_data gracefully without setting baggage."""

    middleware = BaggageMiddleware()
    ctx = _make_channel_data_turn_context(
        channel_id=ChannelId(channel="msteams"),  # No sub_channel
        channel_data="not valid json",  # Non-JSON string
    )

    captured_channel_link = None

    async def logic():
        nonlocal captured_channel_link
        captured_channel_link = baggage.get_baggage(CHANNEL_LINK_KEY)

    await middleware.on_turn(ctx, logic)

    # Should not set ChannelLink, should fail gracefully
    assert captured_channel_link is None

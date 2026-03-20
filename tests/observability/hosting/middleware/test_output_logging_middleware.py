# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents.activity import (
    Activity,
    ChannelAccount,
    ConversationAccount,
)
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.observability.hosting.middleware.output_logging_middleware import (
    A365_PARENT_TRACEPARENT_KEY,
    OutputLoggingMiddleware,
)


def _make_turn_context(
    activity_type: str = "message",
    activity_name: str | None = None,
    text: str = "Hello",
    recipient_tenant_id: str = "tenant-123",
    recipient_agentic_app_id: str = "agent-app-id",
) -> TurnContext:
    """Create a TurnContext with a test activity."""
    kwargs: dict = {
        "type": activity_type,
        "text": text,
        "from_property": ChannelAccount(
            aad_object_id="caller-id",
            name="Caller",
            agentic_user_id="caller-upn",
            tenant_id="caller-tenant-id",
        ),
        "recipient": ChannelAccount(
            tenant_id=recipient_tenant_id,
            role="agenticAppInstance",
            name="Agent One",
            agentic_app_id=recipient_agentic_app_id,
            aad_object_id="agent-auid",
            agentic_user_id="agent-upn",
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
async def test_output_logging_registers_send_handler():
    """OutputLoggingMiddleware should register an on_send_activities handler."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context()

    initial_handler_count = len(ctx._on_send_activities)

    async def logic():
        pass

    await middleware.on_turn(ctx, logic)

    assert len(ctx._on_send_activities) == initial_handler_count + 1


@pytest.mark.asyncio
async def test_output_logging_passes_through_without_recipient():
    """Should pass through without registering handlers if no recipient."""
    middleware = OutputLoggingMiddleware()
    activity = Activity(
        type="message",
        text="Hello",
        from_property=ChannelAccount(name="Caller"),
        conversation=ConversationAccount(id="conv-id"),
        service_url="https://example.com",
    )
    # Remove recipient so agent details cannot be derived
    activity.recipient = None
    adapter = MagicMock()
    ctx = TurnContext(adapter, activity)

    logic_called = False

    async def logic():
        nonlocal logic_called
        logic_called = True

    await middleware.on_turn(ctx, logic)

    assert logic_called is True
    assert len(ctx._on_send_activities) == 0


@pytest.mark.asyncio
async def test_output_logging_passes_through_without_tenant():
    """Should pass through without registering handlers if no tenant id."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context(recipient_tenant_id=None)

    logic_called = False

    async def logic():
        nonlocal logic_called
        logic_called = True

    await middleware.on_turn(ctx, logic)

    assert logic_called is True
    assert len(ctx._on_send_activities) == 0


@pytest.mark.asyncio
async def test_send_handler_skips_non_message_activities():
    """Send handler should skip non-message activities and call send_next."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context()

    await middleware.on_turn(ctx, AsyncMock())

    # Get the registered handler
    handler = ctx._on_send_activities[-1]

    # Create non-message activities
    activities = [Activity(type="typing")]
    send_next = AsyncMock()

    await handler(ctx, activities, send_next)
    send_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_handler_creates_output_scope_for_messages():
    """Send handler should create an OutputScope for message activities and dispose on success."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context()

    await middleware.on_turn(ctx, AsyncMock())

    handler = ctx._on_send_activities[-1]

    activities = [Activity(type="message", text="Reply message")]
    send_next = AsyncMock()

    with patch(
        "microsoft_agents_a365.observability.hosting.middleware"
        ".output_logging_middleware.OutputScope"
    ) as mock_output_scope_cls:
        mock_scope = MagicMock()
        mock_output_scope_cls.start.return_value = mock_scope

        await handler(ctx, activities, send_next)

        mock_output_scope_cls.start.assert_called_once()
        send_next.assert_awaited_once()
        mock_scope.dispose.assert_called_once()
        mock_scope.record_error.assert_not_called()


@pytest.mark.asyncio
async def test_send_handler_uses_parent_span_from_turn_state():
    """Send handler should pass parent_context from turn_state to OutputScope."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context()

    traceparent = "00-1af7651916cd43dd8448eb211c80319c-c7ad6b7169203331-01"
    ctx.turn_state[A365_PARENT_TRACEPARENT_KEY] = traceparent

    await middleware.on_turn(ctx, AsyncMock())

    handler = ctx._on_send_activities[-1]

    activities = [Activity(type="message", text="Reply")]
    send_next = AsyncMock()

    with patch(
        "microsoft_agents_a365.observability.hosting.middleware"
        ".output_logging_middleware.OutputScope"
    ) as mock_output_scope_cls:
        mock_scope = MagicMock()
        mock_output_scope_cls.start.return_value = mock_scope

        await handler(ctx, activities, send_next)

        call_kwargs = mock_output_scope_cls.start.call_args
        # parent_context should be set (extracted from traceparent header)
        assert "parent_context" in call_kwargs.kwargs
        assert call_kwargs.kwargs["parent_context"] is not None


@pytest.mark.asyncio
async def test_send_handler_rethrows_errors():
    """Send handler should re-throw errors from send_next after recording them."""
    middleware = OutputLoggingMiddleware()
    ctx = _make_turn_context()

    await middleware.on_turn(ctx, AsyncMock())

    handler = ctx._on_send_activities[-1]

    activities = [Activity(type="message", text="Reply")]
    send_error = RuntimeError("send pipeline failed")
    send_next = AsyncMock(side_effect=send_error)

    with patch(
        "microsoft_agents_a365.observability.hosting.middleware"
        ".output_logging_middleware.OutputScope"
    ) as mock_output_scope_cls:
        mock_scope = MagicMock()
        mock_output_scope_cls.start.return_value = mock_scope

        with pytest.raises(RuntimeError, match="send pipeline failed"):
            await handler(ctx, activities, send_next)

        mock_scope.record_error.assert_called_once_with(send_error)
        mock_scope.dispose.assert_called_once()

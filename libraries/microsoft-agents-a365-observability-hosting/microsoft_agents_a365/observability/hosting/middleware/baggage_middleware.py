# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Middleware that propagates OpenTelemetry baggage context derived from TurnContext."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from microsoft_agents.activity import ActivityEventNames, ActivityTypes
from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.observability.core.middleware.baggage_builder import BaggageBuilder

from ..scope_helpers.populate_baggage import populate


class BaggageMiddleware:
    """Middleware that propagates OpenTelemetry baggage context derived from TurnContext.

    Async replies (ContinueConversation) are passed through without baggage setup.
    """

    async def on_turn(
        self,
        context: TurnContext,
        logic: Callable[[TurnContext], Awaitable],
    ) -> None:
        activity = context.activity
        is_async_reply = (
            activity is not None
            and activity.type == ActivityTypes.event
            and activity.name == ActivityEventNames.continue_conversation
        )

        if is_async_reply:
            await logic()
            return

        builder = BaggageBuilder()
        populate(builder, context)
        baggage_scope = builder.build()

        with baggage_scope:
            await logic()

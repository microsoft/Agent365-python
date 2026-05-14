# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Middleware that creates OutputScope spans for outgoing messages."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from microsoft_agents.activity import Activity
from microsoft_agents.hosting.core.turn_context import TurnContext
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
)
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.models.user_details import UserDetails
from microsoft_agents_a365.observability.core.request import Request
from microsoft_agents_a365.observability.core.span_details import SpanDetails
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from microsoft_agents_a365.observability.core.utils import extract_context_from_headers

logger = logging.getLogger(__name__)

# TurnState key for the parent trace context (W3C traceparent string).
A365_PARENT_TRACEPARENT_KEY = "A365ParentTraceparent"


def _derive_agent_details(context: TurnContext) -> AgentDetails | None:
    """Derive target agent details from the activity recipient.

    Returns ``None`` when the activity is not an agentic request or the
    recipient is missing, so callers can short-circuit without emitting
    spans with empty identifiers.
    """
    activity = context.activity
    if not activity.is_agentic_request():
        return None
    recipient = getattr(activity, "recipient", None)
    if not recipient:
        return None
    return AgentDetails(
        agent_id=activity.get_agentic_instance_id() or "",
        agent_name=getattr(recipient, "name", None),
        agentic_user_id=getattr(recipient, "aad_object_id", None),
        agentic_user_email=activity.get_agentic_user(),
        agent_description=getattr(recipient, "role", None),
        tenant_id=getattr(recipient, "tenant_id", None),
    )


def _derive_user_details(context: TurnContext) -> UserDetails | None:
    """Derive user identity details from the activity from property."""
    frm = getattr(context.activity, "from_property", None)
    if not frm:
        return None
    return UserDetails(
        user_id=getattr(frm, "aad_object_id", None),
        user_name=getattr(frm, "name", None),
    )


def _derive_conversation_id(context: TurnContext) -> str | None:
    """Derive conversation id from the TurnContext."""
    conv = getattr(context.activity, "conversation", None)
    return conv.id if conv else None


def _derive_channel(
    context: TurnContext,
) -> dict[str, str | None]:
    """Derive channel (name and link) from TurnContext."""
    channel_id = getattr(context.activity, "channel_id", None)
    channel_name: str | None = None
    sub_channel: str | None = None
    if channel_id is not None:
        if isinstance(channel_id, str):
            channel_name = channel_id
        elif hasattr(channel_id, "channel"):
            channel_name = channel_id.channel
            sub_channel = channel_id.sub_channel
    return {"name": channel_name, "link": sub_channel}


class OutputLoggingMiddleware:
    """Middleware that creates :class:`microsoft_agents_a365.observability.core.spans_scopes.output_scope.OutputScope` spans for outgoing messages.

    Links to a parent span when :data:`~microsoft_agents_a365.observability.hosting.middleware.output_logging_middleware.A365_PARENT_TRACEPARENT_KEY` is set in
    ``turn_state``.

    **Privacy note:** Outgoing message content is captured verbatim as span
    attributes and exported to the configured telemetry backend.
    """

    async def on_turn(
        self,
        context: TurnContext,
        logic: Callable[[TurnContext], Awaitable],
    ) -> None:
        agent_details = _derive_agent_details(context)

        if not agent_details:
            await logic()
            return

        user_details = _derive_user_details(context)
        conversation_id = _derive_conversation_id(context)
        channel = _derive_channel(context)

        context.on_send_activities(
            self._create_send_handler(
                context,
                agent_details,
                user_details,
                conversation_id,
                channel,
            )
        )

        await logic()

    def _create_send_handler(
        self,
        turn_context: TurnContext,
        agent_details: AgentDetails,
        user_details: UserDetails | None,
        conversation_id: str | None,
        channel: dict[str, str | None],
    ) -> Callable:
        """Create a send handler that wraps outgoing messages in OutputScope spans.

        Reads parent span ref lazily so the agent handler can set it during ``logic()``.
        """

        async def handler(
            ctx: TurnContext,
            activities: list[Activity],
            send_next: Callable,
        ) -> None:
            messages = [
                a.text for a in activities if getattr(a, "type", None) == "message" and a.text
            ]

            if not messages:
                await send_next()
                return

            traceparent: str | None = turn_context.turn_state.get(A365_PARENT_TRACEPARENT_KEY)
            parent_context = None
            if traceparent:
                parent_context = extract_context_from_headers({"traceparent": traceparent})
            else:
                logger.warning(
                    "[OutputLoggingMiddleware] No traceparent in turn_state under "
                    "'%s'. OutputScope will not be linked to a parent.",
                    A365_PARENT_TRACEPARENT_KEY,
                )

            request = Request(
                conversation_id=conversation_id,
            )

            span_details = SpanDetails(parent_context=parent_context) if parent_context else None

            output_scope = OutputScope.start(
                request=request,
                response=Response(messages=messages),
                agent_details=agent_details,
                user_details=user_details,
                span_details=span_details,
            )

            # Set additional attributes on the scope
            output_scope.set_tag_maybe(CHANNEL_NAME_KEY, channel.get("name"))
            output_scope.set_tag_maybe(CHANNEL_LINK_KEY, channel.get("link"))

            try:
                await send_next()
            except Exception as error:
                output_scope.record_error(error)
                raise
            finally:
                output_scope.dispose()

        return handler

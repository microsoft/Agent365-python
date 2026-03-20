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
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from microsoft_agents_a365.observability.core.models.caller_details import CallerDetails
from microsoft_agents_a365.observability.core.models.response import Response
from microsoft_agents_a365.observability.core.spans_scopes.output_scope import OutputScope
from microsoft_agents_a365.observability.core.tenant_details import TenantDetails
from microsoft_agents_a365.observability.core.utils import extract_context_from_headers

from ..scope_helpers.utils import (
    get_execution_type_pair,
)

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
        agent_auid=getattr(recipient, "aad_object_id", None),
        agent_upn=activity.get_agentic_user(),
        agent_description=getattr(recipient, "role", None),
        tenant_id=getattr(recipient, "tenant_id", None),
    )


def _derive_tenant_details(context: TurnContext) -> TenantDetails | None:
    """Derive tenant details from the activity recipient."""
    tenant_id = getattr(getattr(context.activity, "recipient", None), "tenant_id", None)
    return TenantDetails(tenant_id=tenant_id) if tenant_id else None


def _derive_caller_details(context: TurnContext) -> CallerDetails | None:
    """Derive caller identity details from the activity from property."""
    frm = getattr(context.activity, "from_property", None)
    if not frm:
        return None
    return CallerDetails(
        caller_id=getattr(frm, "aad_object_id", None),
        caller_upn=getattr(frm, "agentic_user_id", None),
        caller_name=getattr(frm, "name", None),
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


def _derive_execution_type(context: TurnContext) -> str | None:
    """Derive execution type from the activity."""
    pairs = list(get_execution_type_pair(context.activity))
    if pairs:
        return pairs[0][1]
    return None


class OutputLoggingMiddleware:
    """Middleware that creates :class:`OutputScope` spans for outgoing messages.

    Links to a parent span when :data:`A365_PARENT_TRACEPARENT_KEY` is set in
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
        tenant_details = _derive_tenant_details(context)

        if not agent_details or not tenant_details:
            await logic()
            return

        caller_details = _derive_caller_details(context)
        conversation_id = _derive_conversation_id(context)
        channel = _derive_channel(context)
        execution_type = _derive_execution_type(context)

        context.on_send_activities(
            self._create_send_handler(
                context,
                agent_details,
                tenant_details,
                caller_details,
                conversation_id,
                channel,
                execution_type,
            )
        )

        await logic()

    def _create_send_handler(
        self,
        turn_context: TurnContext,
        agent_details: AgentDetails,
        tenant_details: TenantDetails,
        caller_details: CallerDetails | None,
        conversation_id: str | None,
        channel: dict[str, str | None],
        execution_type: str | None,
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

            output_scope = OutputScope.start(
                agent_details=agent_details,
                tenant_details=tenant_details,
                response=Response(messages=messages),
                parent_context=parent_context,
            )

            # Set additional attributes on the scope
            output_scope.set_tag_maybe(GEN_AI_CONVERSATION_ID_KEY, conversation_id)
            output_scope.set_tag_maybe(GEN_AI_EXECUTION_TYPE_KEY, execution_type)
            output_scope.set_tag_maybe(CHANNEL_NAME_KEY, channel.get("name"))
            output_scope.set_tag_maybe(CHANNEL_LINK_KEY, channel.get("link"))

            if caller_details:
                output_scope.set_tag_maybe(USER_ID_KEY, caller_details.caller_id)
                output_scope.set_tag_maybe(USER_EMAIL_KEY, caller_details.caller_upn)
                output_scope.set_tag_maybe(USER_NAME_KEY, caller_details.caller_name)

            try:
                await send_next()
            except Exception as error:
                output_scope.record_error(error)
                raise
            finally:
                output_scope.dispose()

        return handler

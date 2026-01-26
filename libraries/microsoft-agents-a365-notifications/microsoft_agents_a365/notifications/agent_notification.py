# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from microsoft_agents.activity import ChannelId
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents.hosting.core.app.state import TurnState
from .models.agent_notification_activity import AgentNotificationActivity, NotificationTypes
from .models.agent_subchannel import AgentSubChannel
from .models.agent_lifecycle_event import AgentLifecycleEvent

TContext = TypeVar("TContext", bound=TurnContext)
TState = TypeVar("TState", bound=TurnState)

AgentHandler = Callable[[TContext, TState, AgentNotificationActivity], Awaitable[None]]


class AgentNotification:
    def __init__(
        self,
        app: Any,
        known_subchannels: Iterable[str | AgentSubChannel] | None = None,
        known_lifecycle_events: Iterable[str | AgentLifecycleEvent] | None = None,
    ):
        self._app = app
        if known_subchannels is None:
            source_subchannels: Iterable[str | AgentSubChannel] = AgentSubChannel
        else:
            source_subchannels = known_subchannels

        self._known_subchannels = {
            normalized
            for normalized in (
                self._normalize_subchannel(sub_channel) for sub_channel in source_subchannels
            )
            if normalized
        }

        if known_lifecycle_events is None:
            source_lifecycle_events: Iterable[str | AgentLifecycleEvent] = AgentLifecycleEvent
        else:
            source_lifecycle_events = known_lifecycle_events

        self._known_lifecycle_events = {
            normalized
            for normalized in (
                self._normalize_lifecycleevent(lifecycle_event)
                for lifecycle_event in source_lifecycle_events
            )
            if normalized
        }

    def on_agent_notification(
        self,
        channel_id: ChannelId,
        **kwargs: Any,
    ):
        registered_channel = channel_id.channel.lower()
        registered_subchannel = (channel_id.sub_channel or "*").lower()

        def route_selector(context: TurnContext) -> bool:
            ch = context.activity.channel_id
            received_channel = (ch.channel if ch else "").lower()
            received_subchannel = (ch.sub_channel if ch and ch.sub_channel else "").lower()
            if received_channel != registered_channel:
                return False
            if registered_subchannel == "*":
                return True
            if registered_subchannel not in self._known_subchannels:
                return False
            return received_subchannel == registered_subchannel

        def create_handler(handler: AgentHandler):
            async def route_handler(context: TurnContext, state: TurnState):
                ana = AgentNotificationActivity(context.activity)
                await handler(context, state, ana)

            return route_handler

        def decorator(handler: AgentHandler):
            route_handler = create_handler(handler)
            self._app.add_route(route_selector, route_handler, **kwargs)
            return route_handler

        return decorator

    def on_agent_lifecycle_notification(
        self,
        lifecycle_event: str,
        **kwargs: Any,
    ):
        def route_selector(context: TurnContext) -> bool:
            ch = context.activity.channel_id
            received_channel = ch.channel if ch else ""
            received_channel = received_channel.lower()
            if received_channel != "agents":
                return False
            if context.activity.name != NotificationTypes.AGENT_LIFECYCLE:
                return False
            if lifecycle_event == "*":
                return True
            if context.activity.value_type not in self._known_lifecycle_events:
                return False
            return True

        def create_handler(handler: AgentHandler):
            async def route_handler(context: TurnContext, state: TurnState):
                ana = AgentNotificationActivity(context.activity)
                await handler(context, state, ana)

            return route_handler

        def decorator(handler: AgentHandler):
            route_handler = create_handler(handler)
            self._app.add_route(route_selector, route_handler, **kwargs)
            return route_handler

        return decorator

    def on_email(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.EMAIL), **kwargs
        )

    def on_word(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.WORD), **kwargs
        )

    def on_excel(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.EXCEL), **kwargs
        )

    def on_powerpoint(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.POWERPOINT), **kwargs
        )

    def on_lifecycle(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_lifecycle_notification("*", **kwargs)

    def on_user_created(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_lifecycle_notification(AgentLifecycleEvent.USERCREATED, **kwargs)

    def on_user_workload_onboarding(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_lifecycle_notification(
            AgentLifecycleEvent.USERWORKLOADONBOARDINGUPDATED, **kwargs
        )

    def on_user_deleted(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        return self.on_lifecycle_notification(AgentLifecycleEvent.USERDELETED, **kwargs)

    @staticmethod
    def _normalize_subchannel(value: str | AgentSubChannel | None) -> str:
        if value is None:
            return ""
        resolved = value.value if isinstance(value, AgentSubChannel) else str(value)
        return resolved.lower().strip()

    @staticmethod
    def _normalize_lifecycleevent(value: str | AgentLifecycleEvent | None) -> str:
        if value is None:
            return ""
        resolved = value.value if isinstance(value, AgentLifecycleEvent) else str(value)
        return resolved.lower().strip()

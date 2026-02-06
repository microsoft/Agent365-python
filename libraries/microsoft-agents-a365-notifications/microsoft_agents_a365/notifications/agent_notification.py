# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from microsoft_agents.activity import ChannelId
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents.hosting.core.app.state import TurnState

from .models.agent_lifecycle_event import AgentLifecycleEvent
from .models.agent_notification_activity import AgentNotificationActivity, NotificationTypes
from .models.agent_subchannel import AgentSubChannel

TContext = TypeVar("TContext", bound=TurnContext)
TState = TypeVar("TState", bound=TurnState)

#: Type alias for agent notification handler functions.
#:
#: Agent handlers are async functions that process notifications from Microsoft 365
#: applications. They receive the turn context, application state, and a typed
#: notification activity wrapper.
#:
#: Args:
#:     context: The turn context for the current conversation turn.
#:     state: The application state for the current turn.
#:     notification: The typed notification activity with parsed entities.
#:
#: Example:
#:     ```python
#:     async def handle_email(
#:         context: TurnContext,
#:         state: TurnState,
#:         notification: AgentNotificationActivity
#:     ) -> None:
#:         email = notification.email
#:         if email:
#:             print(f"Processing email: {email.id}")
#:     ```
AgentHandler = Callable[[TContext, TState, AgentNotificationActivity], Awaitable[None]]


class AgentNotification:
    """Handler for agent notifications from Microsoft 365 applications.

    This class provides decorators for registering handlers that respond to notifications
    from various Microsoft 365 channels and subchannels. It supports routing based on
    channel ID, subchannel, and lifecycle events.

    Args:
        app: The application instance that will handle the routed notifications.
        known_subchannels: Optional iterable of recognized subchannels. If None,
            defaults to all values in the AgentSubChannel enum.
        known_lifecycle_events: Optional iterable of recognized lifecycle events. If None,
            defaults to all values in the AgentLifecycleEvent enum.

    Example:
        ```python
        from microsoft_agents.hosting import Application
        from microsoft_agents_a365.notifications import AgentNotification

        app = Application()
        notifications = AgentNotification(app)

        @notifications.on_email()
        async def handle_email(context, state, notification):
            email = notification.email
            if email:
                await context.send_activity(f"Received email: {email.id}")
        ```
    """

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
        """Register a handler for notifications from a specific channel and subchannel.

        This decorator registers a handler function to be called when a notification is
        received from the specified channel and optional subchannel. The handler will
        receive a typed AgentNotificationActivity wrapper.

        Args:
            channel_id: The channel ID specifying the channel and optional subchannel
                to listen for. Use "*" as the subchannel to match all subchannels.
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            from microsoft_agents.activity import ChannelId

            @notifications.on_agent_notification(
                ChannelId(channel="agents", sub_channel="email")
            )
            async def handle_custom_channel(context, state, notification):
                print(f"Received notification on {notification.channel}/{notification.sub_channel}")
            ```
        """
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
        """Register a handler for agent lifecycle event notifications.

        This decorator registers a handler function to be called when lifecycle events
        occur, such as user creation, deletion, or workload onboarding updates.

        Args:
            lifecycle_event: The lifecycle event to listen for. Use "*" to match all
                lifecycle events, or specify a specific event from AgentLifecycleEvent.
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_agent_lifecycle_notification("agenticuseridentitycreated")
            async def handle_user_created(context, state, notification):
                print("New user created")
            ```
        """

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
        """Register a handler for Outlook email notifications.

        This is a convenience decorator that registers a handler for notifications
        from the email subchannel.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_email()
            async def handle_email(context, state, notification):
                email = notification.email
                if email:
                    print(f"Received email: {email.id}")
                    # Send a response
                    response = EmailResponse.create_email_response_activity(
                        "<p>Thank you for your email.</p>"
                    )
                    await context.send_activity(response)
            ```
        """
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.EMAIL), **kwargs
        )

    def on_word(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for Microsoft Word comment notifications.

        This is a convenience decorator that registers a handler for notifications
        from the Word subchannel.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_word()
            async def handle_word_comment(context, state, notification):
                comment = notification.wpx_comment
                if comment:
                    print(f"Received Word comment: {comment.comment_id}")
            ```
        """
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.WORD), **kwargs
        )

    def on_excel(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for Microsoft Excel comment notifications.

        This is a convenience decorator that registers a handler for notifications
        from the Excel subchannel.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_excel()
            async def handle_excel_comment(context, state, notification):
                comment = notification.wpx_comment
                if comment:
                    print(f"Received Excel comment: {comment.comment_id}")
            ```
        """
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.EXCEL), **kwargs
        )

    def on_powerpoint(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for Microsoft PowerPoint comment notifications.

        This is a convenience decorator that registers a handler for notifications
        from the PowerPoint subchannel.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_powerpoint()
            async def handle_powerpoint_comment(context, state, notification):
                comment = notification.wpx_comment
                if comment:
                    print(f"Received PowerPoint comment: {comment.comment_id}")
            ```
        """
        return self.on_agent_notification(
            ChannelId(channel="agents", sub_channel=AgentSubChannel.POWERPOINT), **kwargs
        )

    def on_lifecycle(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for all agent lifecycle event notifications.

        This is a convenience decorator that registers a handler for all lifecycle
        events using the wildcard "*" matcher.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_lifecycle()
            async def handle_any_lifecycle_event(context, state, notification):
                print(f"Lifecycle event type: {notification.notification_type}")
            ```
        """
        return self.on_lifecycle_notification("*", **kwargs)

    def on_user_created(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for user creation lifecycle events.

        This is a convenience decorator that registers a handler specifically for
        agentic user identity creation events.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_user_created()
            async def handle_user_created(context, state, notification):
                print("New agentic user identity created")
            ```
        """
        return self.on_lifecycle_notification(AgentLifecycleEvent.USERCREATED, **kwargs)

    def on_user_workload_onboarding(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for user workload onboarding update events.

        This is a convenience decorator that registers a handler for events that occur
        when a user's workload onboarding status is updated.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_user_workload_onboarding()
            async def handle_onboarding_update(context, state, notification):
                print("User workload onboarding status updated")
            ```
        """
        return self.on_lifecycle_notification(
            AgentLifecycleEvent.USERWORKLOADONBOARDINGUPDATED, **kwargs
        )

    def on_user_deleted(
        self, **kwargs: Any
    ) -> Callable[[AgentHandler], Callable[[TurnContext, TurnState], Awaitable[None]]]:
        """Register a handler for user deletion lifecycle events.

        This is a convenience decorator that registers a handler specifically for
        agentic user identity deletion events.

        Args:
            **kwargs: Additional keyword arguments passed to the app's add_route method.

        Returns:
            A decorator function that registers the handler with the application.

        Example:
            ```python
            @notifications.on_user_deleted()
            async def handle_user_deleted(context, state, notification):
                print("Agentic user identity deleted")
            ```
        """
        return self.on_lifecycle_notification(AgentLifecycleEvent.USERDELETED, **kwargs)

    @staticmethod
    def _normalize_subchannel(value: str | AgentSubChannel | None) -> str:
        """Normalize a subchannel value to a lowercase string.

        Args:
            value: The subchannel value to normalize, either as an enum or string.

        Returns:
            The normalized lowercase subchannel string, or empty string if None.
        """
        if value is None:
            return ""
        resolved = value.value if isinstance(value, AgentSubChannel) else str(value)
        return resolved.lower().strip()

    @staticmethod
    def _normalize_lifecycleevent(value: str | AgentLifecycleEvent | None) -> str:
        """Normalize a lifecycle event value to a lowercase string.

        Args:
            value: The lifecycle event value to normalize, either as an enum or string.

        Returns:
            The normalized lowercase lifecycle event string, or empty string if None.
        """
        if value is None:
            return ""
        resolved = value.value if isinstance(value, AgentLifecycleEvent) else str(value)
        return resolved.lower().strip()

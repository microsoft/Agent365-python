# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for AgentNotification class routing decorators."""

from unittest.mock import MagicMock

from microsoft_agents_a365.notifications import AgentHandler, AgentNotification, RouteHandler
from microsoft_agents_a365.notifications.models.agent_lifecycle_event import AgentLifecycleEvent
from microsoft_agents_a365.notifications.models.agent_subchannel import AgentSubChannel


class TestAgentNotificationTypeAliases:
    """Tests verifying the public type aliases are importable and properly defined."""

    def test_agent_handler_is_importable(self):
        """AgentHandler type alias can be imported from the package."""
        assert AgentHandler is not None

    def test_route_handler_is_importable(self):
        """RouteHandler type alias can be imported from the package."""
        assert RouteHandler is not None

    def test_agent_handler_is_type_alias(self):
        """AgentHandler is a TypeAlias (not a TypeVar)."""
        import typing

        # TypeAlias values are just the underlying type, not TypeVar instances
        assert not isinstance(AgentHandler, typing.TypeVar)

    def test_route_handler_is_type_alias(self):
        """RouteHandler is a TypeAlias (not a TypeVar)."""
        import typing

        assert not isinstance(RouteHandler, typing.TypeVar)


class TestAgentNotificationRouting:
    """Tests verifying that convenience decorator methods register routes correctly."""

    def _make_app(self):
        """Return a mock app with an add_route spy."""
        app = MagicMock()
        app.add_route = MagicMock()
        return app

    def test_on_email_calls_add_route(self):
        """on_email() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_email()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_word_calls_add_route(self):
        """on_word() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_word()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_excel_calls_add_route(self):
        """on_excel() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_excel()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_powerpoint_calls_add_route(self):
        """on_powerpoint() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_powerpoint()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_lifecycle_calls_add_route(self):
        """on_lifecycle() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_lifecycle()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_user_created_calls_add_route(self):
        """on_user_created() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_user_created()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_user_workload_onboarding_calls_add_route(self):
        """on_user_workload_onboarding() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_user_workload_onboarding()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()

    def test_on_user_deleted_calls_add_route(self):
        """on_user_deleted() registers a route via app.add_route."""
        app = self._make_app()
        notifications = AgentNotification(app)

        @notifications.on_user_deleted()
        async def handler(context, state, notification):
            pass

        app.add_route.assert_called_once()


class TestAgentNotificationRouteSelector:
    """Tests verifying that the route selector logic correctly matches activities."""

    def _make_turn_context(self, channel: str, sub_channel: str | None = None):
        """Create a mock TurnContext with the given channel_id values.

        Args:
            channel: The channel identifier (e.g., "agents").
            sub_channel: The optional sub-channel identifier (e.g., "email").
        """
        channel_id = MagicMock()
        channel_id.channel = channel
        channel_id.sub_channel = sub_channel

        activity = MagicMock()
        activity.channel_id = channel_id

        context = MagicMock()
        context.activity = activity
        return context

    def _make_lifecycle_context(self, value_type: str):
        """Create a mock TurnContext for a lifecycle notification.

        Args:
            value_type: The lifecycle event type identifier (e.g.,
                ``AgentLifecycleEvent.USERCREATED.value``).
        """
        from microsoft_agents_a365.notifications.models.notification_types import NotificationTypes

        channel_id = MagicMock()
        channel_id.channel = "agents"
        channel_id.sub_channel = None

        activity = MagicMock()
        activity.channel_id = channel_id
        activity.name = NotificationTypes.AGENT_LIFECYCLE
        activity.value_type = value_type

        context = MagicMock()
        context.activity = activity
        return context

    def test_on_email_selector_matches_email_subchannel(self):
        """Route selector registered by on_email() matches the email subchannel."""
        app = MagicMock()
        captured_selector = None

        def capture_add_route(selector, handler, **kwargs):
            nonlocal captured_selector
            captured_selector = selector

        app.add_route = capture_add_route
        notifications = AgentNotification(app)

        @notifications.on_email()
        async def handler(context, state, notification):
            pass

        assert captured_selector is not None
        ctx = self._make_turn_context("agents", AgentSubChannel.EMAIL.value)
        assert captured_selector(ctx) is True

    def test_on_email_selector_rejects_word_subchannel(self):
        """Route selector registered by on_email() rejects the word subchannel."""
        app = MagicMock()
        captured_selector = None

        def capture_add_route(selector, handler, **kwargs):
            nonlocal captured_selector
            captured_selector = selector

        app.add_route = capture_add_route
        notifications = AgentNotification(app)

        @notifications.on_email()
        async def handler(context, state, notification):
            pass

        assert captured_selector is not None
        ctx = self._make_turn_context("agents", AgentSubChannel.WORD.value)
        assert captured_selector(ctx) is False

    def test_on_lifecycle_selector_matches_any_lifecycle_event(self):
        """Route selector from on_lifecycle() matches any lifecycle event (wildcard)."""
        app = MagicMock()
        captured_selector = None

        def capture_add_route(selector, handler, **kwargs):
            nonlocal captured_selector
            captured_selector = selector

        app.add_route = capture_add_route
        notifications = AgentNotification(app)

        @notifications.on_lifecycle()
        async def handler(context, state, notification):
            pass

        assert captured_selector is not None
        ctx = self._make_lifecycle_context(AgentLifecycleEvent.USERCREATED.value)
        assert captured_selector(ctx) is True

    def test_on_user_created_selector_matches_user_created_event(self):
        """Route selector from on_user_created() matches the user created event."""
        app = MagicMock()
        captured_selector = None

        def capture_add_route(selector, handler, **kwargs):
            nonlocal captured_selector
            captured_selector = selector

        app.add_route = capture_add_route
        notifications = AgentNotification(app)

        @notifications.on_user_created()
        async def handler(context, state, notification):
            pass

        assert captured_selector is not None
        ctx = self._make_lifecycle_context(AgentLifecycleEvent.USERCREATED.value)
        assert captured_selector(ctx) is True

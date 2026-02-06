# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any, Optional, Type, TypeVar
from microsoft_agents.activity import Activity
from .notification_types import NotificationTypes
from .email_reference import EmailReference
from .wpx_comment import WpxComment

TModel = TypeVar("TModel")


class AgentNotificationActivity:
    """Wrapper around an Activity object with typed notification entities.

    This class provides convenient access to typed notification entities extracted from
    an Activity's entities collection. It automatically parses and validates email
    notifications, Word/PowerPoint/Excel comments, and lifecycle events at construction
    time.

    Args:
        activity: The Activity object to wrap. Must not be None.

    Raises:
        ValueError: If the activity parameter is None.

    Attributes:
        activity: The underlying Activity object.

    Example:
        ```python
        async def email_handler(context: TurnContext, state: TurnState, notification: AgentNotificationActivity):
            email = notification.email
            if email:
                print(f"Received email: {email.id}")
                print(f"Body: {email.html_body}")
        ```
    """

    def __init__(self, activity: Activity):
        if not activity:
            raise ValueError("activity parameter is required and cannot be None")
        self.activity = activity
        self._email: Optional[EmailReference] = None
        self._wpx_comment: Optional[WpxComment] = None
        self._notification_type: Optional[NotificationTypes] = None

        entities = self.activity.entities or []
        for ent in entities:
            etype = ent.type.lower()
            payload = getattr(ent, "additional_properties", ent)

            if etype == NotificationTypes.EMAIL_NOTIFICATION.lower() and self._email is None:
                try:
                    self._email = EmailReference.model_validate(payload)
                    self._notification_type = NotificationTypes.EMAIL_NOTIFICATION
                except Exception:
                    self._email = None

            if etype == NotificationTypes.WPX_COMMENT.lower() and self._wpx_comment is None:
                try:
                    self._wpx_comment = WpxComment.model_validate(payload)
                    self._notification_type = NotificationTypes.WPX_COMMENT
                except Exception:
                    self._wpx_comment = None

        # Set notification type from activity name if not already set
        if self._notification_type is None:
            self._notification_type = (
                NotificationTypes.AGENT_LIFECYCLE
                if NotificationTypes(self.activity.name) is NotificationTypes.AGENT_LIFECYCLE
                else None
            )

    # ---- passthroughs ----
    @property
    def channel(self) -> Optional[str]:
        """The channel identifier from the activity's channel_id.

        Returns:
            The channel name (e.g., 'agents', 'msteams') or None if not available.
        """
        ch = self.activity.channel_id
        return ch.channel if ch else None

    @property
    def sub_channel(self) -> Optional[str]:
        """The subchannel identifier from the activity's channel_id.

        Returns:
            The subchannel name (e.g., 'email', 'word') or None if not available.
        """
        ch = self.activity.channel_id
        return ch.sub_channel if ch else None

    @property
    def value(self) -> Any:
        """The value payload from the activity.

        Returns:
            The activity's value, which may contain additional notification data.
        """
        return self.activity.value

    @property
    def type(self) -> Optional[str]:
        """The activity type.

        Returns:
            The type of the activity (e.g., 'message', 'event') or None if not set.
        """
        return self.activity.type

    # --- typed entities available directly on the activity ---
    @property
    def email(self) -> Optional[EmailReference]:
        """The parsed email reference entity, if present.

        Returns:
            An EmailReference object if an email notification entity was found and
            successfully parsed, otherwise None.
        """
        return self._email

    @property
    def wpx_comment(self) -> Optional[WpxComment]:
        """The parsed Word/PowerPoint/Excel comment entity, if present.

        Returns:
            A WpxComment object if a comment entity was found and successfully parsed,
            otherwise None.
        """
        return self._wpx_comment

    @property
    def notification_type(self) -> Optional[NotificationTypes]:
        """The detected notification type.

        Returns:
            The NotificationTypes enum value indicating the type of notification
            (EMAIL_NOTIFICATION, WPX_COMMENT, or AGENT_LIFECYCLE), or None if the
            notification type could not be determined.
        """
        return self._notification_type

    # Generic escape hatch
    def as_model(self, model: Type[TModel]) -> Optional[TModel]:
        """Parse the activity value as a custom model type.

        This method provides a generic way to validate and parse the activity's value
        payload into any Pydantic model type. Useful for custom notification types not
        directly supported by the typed properties.

        Args:
            model: A Pydantic model class to validate and parse the activity value into.

        Returns:
            An instance of the specified model type if validation succeeds, otherwise None.

        Example:
            ```python
            from pydantic import BaseModel

            class CustomNotification(BaseModel):
                custom_field: str

            notification = AgentNotificationActivity(activity)
            custom = notification.as_model(CustomNotification)
            if custom:
                print(custom.custom_field)
            ```
        """
        try:
            return model.model_validate(self.value or {})
        except Exception:
            return None

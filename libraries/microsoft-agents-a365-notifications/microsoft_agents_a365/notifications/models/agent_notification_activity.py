from typing import Any, Optional, Type, TypeVar
from microsoft_agents.activity import Activity
from .notification_types import NotificationTypes
from .email_reference import EmailReference
from .wpx_comment import WpxComment

TModel = TypeVar("TModel")


class AgentNotificationActivity:
    """Light wrapper around an Activity object with typed entities parsed at create time."""

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
        ch = self.activity.channel_id
        return ch.channel if ch else None

    @property
    def sub_channel(self) -> Optional[str]:
        ch = self.activity.channel_id
        return ch.sub_channel if ch else None

    @property
    def value(self) -> Any:
        return self.activity.value

    @property
    def type(self) -> Optional[str]:
        return self.activity.type

    # --- typed entities available directly on the activity ---
    @property
    def email(self) -> Optional[EmailReference]:
        return self._email

    @property
    def wpx_comment(self) -> Optional[WpxComment]:
        return self._wpx_comment

    @property
    def notification_type(self) -> Optional[NotificationTypes]:
        return self._notification_type

    # Generic escape hatch
    def as_model(self, model: Type[TModel]) -> Optional[TModel]:
        try:
            return model.model_validate(self.value or {})
        except Exception:
            return None

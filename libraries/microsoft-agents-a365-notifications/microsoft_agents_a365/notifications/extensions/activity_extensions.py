# Copyright (c) Microsoft. All rights reserved.

"""
Activity Extensions for Notifications

This module provides helper methods for manipulating Activity objects
in the context of Agent notifications. It includes utilities for:
- Creating activities with notification entities
- Extracting typed entities from activities
- Activity validation and manipulation
"""

from typing import Optional, Type, TypeVar, List
from microsoft_agents.activity import Activity
from microsoft_agents.activity.entity import Entity
from ..models.email_reference import EmailReference
from ..models.wpx_comment import WpxComment
from ..models.email_response import EmailResponse
from ..models.notification_types import NotificationTypes

TEntity = TypeVar("TEntity", bound=Entity)


class ActivityExtensions:
    """Helper methods for working with Activity objects in notification contexts."""

    @staticmethod
    def create_notification_activity(
        entity: Entity,
        activity_type: str = "message",
    ) -> Activity:
        """Create a new Activity with a notification entity.

        Args:
            entity: The notification entity to attach to the activity.
            activity_type: The type of activity to create (default: "message").

        Returns:
            A new Activity instance with the entity attached.
        """
        activity = Activity(type=activity_type)
        if activity.entities is None:
            activity.entities = []
        activity.entities.append(entity)
        return activity

    @staticmethod
    def create_email_notification_activity(
        email_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> Activity:
        """Create a new Activity with an EmailReference entity.

        Args:
            email_id: The email identifier.
            conversation_id: The conversation identifier.
            html_body: The HTML body of the email.

        Returns:
            A new Activity instance with an EmailReference entity attached.
        """
        email_ref = EmailReference(
            id=email_id,
            conversation_id=conversation_id,
            html_body=html_body,
        )
        return ActivityExtensions.create_notification_activity(email_ref)

    @staticmethod
    def create_wpx_comment_activity(
        odata_id: Optional[str] = None,
        document_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None,
        comment_id: Optional[str] = None,
    ) -> Activity:
        """Create a new Activity with a WpxComment entity.

        Args:
            odata_id: The OData identifier.
            document_id: The document identifier.
            parent_comment_id: The parent comment identifier.
            comment_id: The comment identifier.

        Returns:
            A new Activity instance with a WpxComment entity attached.
        """
        wpx_comment = WpxComment(
            odata_id=odata_id,
            document_id=document_id,
            parent_comment_id=parent_comment_id,
            comment_id=comment_id,
        )
        return ActivityExtensions.create_notification_activity(wpx_comment)

    @staticmethod
    def get_entity_by_type(activity: Activity, entity_type: Type[TEntity]) -> Optional[TEntity]:
        """Extract a typed entity from an Activity.

        Args:
            activity: The activity to search.
            entity_type: The type of entity to extract.

        Returns:
            The first entity matching the type, or None if not found.
        """
        if not activity or not activity.entities:
            return None

        for entity in activity.entities:
            # Check if entity is already the correct type
            if isinstance(entity, entity_type):
                return entity

            # Don't try to validate if the type attributes don't match
            # This prevents creating entities from empty dicts
            if not ActivityExtensions._entity_type_matches(entity, entity_type):
                continue

            # Try to validate as the entity type
            try:
                payload = getattr(entity, "additional_properties", entity)
                return entity_type.model_validate(payload)
            except Exception:
                continue

        return None

    @staticmethod
    def _entity_type_matches(entity: Entity, entity_type: Type[TEntity]) -> bool:
        """Check if an entity's type attribute matches the target entity type.

        Args:
            entity: The entity to check.
            entity_type: The target entity type.

        Returns:
            True if the entity type matches, False otherwise.
        """
        if not hasattr(entity, "type"):
            return True  # If no type attribute, allow validation attempt

        # Get the expected type value from the entity_type class
        try:
            # Create a temporary instance to get the type value
            temp = entity_type()
            expected_type = temp.type
            entity_type_value = entity.type

            # Compare the type values (handle both string and enum)
            return str(expected_type).lower() == str(entity_type_value).lower()
        except Exception:
            return True  # If we can't determine, allow validation attempt

    @staticmethod
    def get_email_reference(activity: Activity) -> Optional[EmailReference]:
        """Extract an EmailReference entity from an Activity.

        Args:
            activity: The activity to search.

        Returns:
            The EmailReference entity if found, None otherwise.
        """
        return ActivityExtensions.get_entity_by_type(activity, EmailReference)

    @staticmethod
    def get_wpx_comment(activity: Activity) -> Optional[WpxComment]:
        """Extract a WpxComment entity from an Activity.

        Args:
            activity: The activity to search.

        Returns:
            The WpxComment entity if found, None otherwise.
        """
        return ActivityExtensions.get_entity_by_type(activity, WpxComment)

    @staticmethod
    def get_email_response(activity: Activity) -> Optional[EmailResponse]:
        """Extract an EmailResponse entity from an Activity.

        Args:
            activity: The activity to search.

        Returns:
            The EmailResponse entity if found, None otherwise.
        """
        return ActivityExtensions.get_entity_by_type(activity, EmailResponse)

    @staticmethod
    def get_entities_by_type(activity: Activity, entity_type: Type[TEntity]) -> List[TEntity]:
        """Extract all entities of a specific type from an Activity.

        Args:
            activity: The activity to search.
            entity_type: The type of entities to extract.

        Returns:
            A list of entities matching the type (may be empty).
        """
        if not activity or not activity.entities:
            return []

        entities = []
        for entity in activity.entities:
            # Check if entity is already the correct type
            if isinstance(entity, entity_type):
                entities.append(entity)
                continue

            # Don't try to validate if the type attributes don't match
            if not ActivityExtensions._entity_type_matches(entity, entity_type):
                continue

            # Try to validate as the entity type
            try:
                payload = getattr(entity, "additional_properties", entity)
                validated_entity = entity_type.model_validate(payload)
                entities.append(validated_entity)
            except Exception:
                continue

        return entities

    @staticmethod
    def has_entity_type(activity: Activity, entity_type_name: str) -> bool:
        """Check if an Activity contains an entity of a specific type.

        Args:
            activity: The activity to check.
            entity_type_name: The type name to search for (case-insensitive).

        Returns:
            True if the activity contains an entity of the specified type.
        """
        if not activity or not activity.entities:
            return False

        entity_type_lower = entity_type_name.lower()
        for entity in activity.entities:
            if hasattr(entity, "type") and entity.type.lower() == entity_type_lower:
                return True

        return False

    @staticmethod
    def is_email_notification(activity: Activity) -> bool:
        """Check if an Activity is an email notification.

        Args:
            activity: The activity to check.

        Returns:
            True if the activity contains an EmailReference entity.
        """
        return ActivityExtensions.has_entity_type(activity, NotificationTypes.EMAIL_NOTIFICATION)

    @staticmethod
    def is_wpx_comment_notification(activity: Activity) -> bool:
        """Check if an Activity is a WPX comment notification.

        Args:
            activity: The activity to check.

        Returns:
            True if the activity contains a WpxComment entity.
        """
        return ActivityExtensions.has_entity_type(activity, NotificationTypes.WPX_COMMENT)

    @staticmethod
    def add_entity(activity: Activity, entity: Entity) -> Activity:
        """Add an entity to an Activity.

        Args:
            activity: The activity to modify.
            entity: The entity to add.

        Returns:
            The modified activity (for method chaining).
        """
        if activity.entities is None:
            activity.entities = []
        activity.entities.append(entity)
        return activity

    @staticmethod
    def clear_entities(activity: Activity) -> Activity:
        """Remove all entities from an Activity.

        Args:
            activity: The activity to modify.

        Returns:
            The modified activity (for method chaining).
        """
        activity.entities = []
        return activity

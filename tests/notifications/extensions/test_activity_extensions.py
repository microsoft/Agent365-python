# Copyright (c) Microsoft. All rights reserved.

"""
Unit tests for ActivityExtensions.

Tests the helper methods for manipulating Activity objects
in notification contexts.
"""

import pytest
from microsoft_agents.activity import Activity
from microsoft_agents_a365.notifications.extensions import ActivityExtensions
from microsoft_agents_a365.notifications.models import (
    EmailReference,
    EmailResponse,
    NotificationTypes,
    WpxComment,
)


class TestActivityExtensions:
    """Test suite for ActivityExtensions class."""

    def test_create_notification_activity_default_type(self):
        """Test creating a notification activity with default type."""
        entity = EmailReference(id="test-email-id")
        activity = ActivityExtensions.create_notification_activity(entity)

        assert activity is not None
        assert activity.type == "message"
        assert activity.entities is not None
        assert len(activity.entities) == 1
        assert activity.entities[0] == entity

    def test_create_notification_activity_custom_type(self):
        """Test creating a notification activity with custom type."""
        entity = WpxComment(comment_id="test-comment")
        activity = ActivityExtensions.create_notification_activity(entity, activity_type="event")

        assert activity is not None
        assert activity.type == "event"
        assert activity.entities is not None
        assert len(activity.entities) == 1

    def test_create_email_notification_activity(self):
        """Test creating an email notification activity."""
        email_id = "email-123"
        conversation_id = "conv-456"
        html_body = "<p>Test email</p>"

        activity = ActivityExtensions.create_email_notification_activity(
            email_id=email_id,
            conversation_id=conversation_id,
            html_body=html_body,
        )

        assert activity is not None
        assert activity.type == "message"
        assert activity.entities is not None
        assert len(activity.entities) == 1

        # Verify the email reference was created correctly
        email_ref = activity.entities[0]
        assert isinstance(email_ref, EmailReference)
        assert email_ref.id == email_id
        assert email_ref.conversation_id == conversation_id
        assert email_ref.html_body == html_body

    def test_create_email_notification_activity_minimal(self):
        """Test creating an email notification activity with minimal parameters."""
        activity = ActivityExtensions.create_email_notification_activity()

        assert activity is not None
        assert activity.type == "message"
        assert activity.entities is not None
        assert len(activity.entities) == 1

        email_ref = activity.entities[0]
        assert isinstance(email_ref, EmailReference)
        assert email_ref.id is None
        assert email_ref.conversation_id is None
        assert email_ref.html_body is None

    def test_create_wpx_comment_activity(self):
        """Test creating a WPX comment activity."""
        odata_id = "odata-123"
        document_id = "doc-456"
        parent_comment_id = "parent-789"
        comment_id = "comment-012"

        activity = ActivityExtensions.create_wpx_comment_activity(
            odata_id=odata_id,
            document_id=document_id,
            parent_comment_id=parent_comment_id,
            comment_id=comment_id,
        )

        assert activity is not None
        assert activity.type == "message"
        assert activity.entities is not None
        assert len(activity.entities) == 1

        wpx_comment = activity.entities[0]
        assert isinstance(wpx_comment, WpxComment)
        assert wpx_comment.odata_id == odata_id
        assert wpx_comment.document_id == document_id
        assert wpx_comment.parent_comment_id == parent_comment_id
        assert wpx_comment.comment_id == comment_id

    def test_create_wpx_comment_activity_minimal(self):
        """Test creating a WPX comment activity with minimal parameters."""
        activity = ActivityExtensions.create_wpx_comment_activity()

        assert activity is not None
        assert activity.entities is not None
        assert len(activity.entities) == 1

        wpx_comment = activity.entities[0]
        assert isinstance(wpx_comment, WpxComment)

    def test_get_entity_by_type_email_reference(self):
        """Test extracting an EmailReference entity from an activity."""
        email_ref = EmailReference(id="test-email", html_body="<p>Test</p>")
        activity = Activity(type="message", entities=[email_ref])

        extracted = ActivityExtensions.get_entity_by_type(activity, EmailReference)

        assert extracted is not None
        assert isinstance(extracted, EmailReference)
        assert extracted.id == "test-email"
        assert extracted.html_body == "<p>Test</p>"

    def test_get_entity_by_type_not_found(self):
        """Test extracting an entity that doesn't exist."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        extracted = ActivityExtensions.get_entity_by_type(activity, WpxComment)

        assert extracted is None

    def test_get_entity_by_type_no_entities(self):
        """Test extracting an entity from an activity with no entities."""
        activity = Activity(type="message")

        extracted = ActivityExtensions.get_entity_by_type(activity, EmailReference)

        assert extracted is None

    def test_get_entity_by_type_none_activity(self):
        """Test extracting an entity from a None activity."""
        extracted = ActivityExtensions.get_entity_by_type(None, EmailReference)

        assert extracted is None

    def test_get_email_reference(self):
        """Test the convenience method for extracting EmailReference."""
        email_ref = EmailReference(id="test-email", conversation_id="conv-123")
        activity = Activity(type="message", entities=[email_ref])

        extracted = ActivityExtensions.get_email_reference(activity)

        assert extracted is not None
        assert isinstance(extracted, EmailReference)
        assert extracted.id == "test-email"
        assert extracted.conversation_id == "conv-123"

    def test_get_wpx_comment(self):
        """Test the convenience method for extracting WpxComment."""
        wpx_comment = WpxComment(comment_id="comment-123", document_id="doc-456")
        activity = Activity(type="message", entities=[wpx_comment])

        extracted = ActivityExtensions.get_wpx_comment(activity)

        assert extracted is not None
        assert isinstance(extracted, WpxComment)
        assert extracted.comment_id == "comment-123"
        assert extracted.document_id == "doc-456"

    def test_get_email_response(self):
        """Test the convenience method for extracting EmailResponse."""
        email_response = EmailResponse(html_body="<p>Response</p>")
        activity = Activity(type="message", entities=[email_response])

        extracted = ActivityExtensions.get_email_response(activity)

        assert extracted is not None
        assert isinstance(extracted, EmailResponse)
        assert extracted.html_body == "<p>Response</p>"

    def test_get_entities_by_type_multiple(self):
        """Test extracting multiple entities of the same type."""
        email1 = EmailReference(id="email-1")
        email2 = EmailReference(id="email-2")
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[email1, wpx, email2])

        emails = ActivityExtensions.get_entities_by_type(activity, EmailReference)

        assert len(emails) == 2
        assert all(isinstance(e, EmailReference) for e in emails)

    def test_get_entities_by_type_empty(self):
        """Test extracting entities when none of the type exist."""
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[wpx])

        emails = ActivityExtensions.get_entities_by_type(activity, EmailReference)

        assert len(emails) == 0

    def test_get_entities_by_type_no_entities(self):
        """Test extracting entities from an activity with no entities."""
        activity = Activity(type="message")

        emails = ActivityExtensions.get_entities_by_type(activity, EmailReference)

        assert len(emails) == 0

    def test_has_entity_type_present(self):
        """Test checking for entity type that is present."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        result = ActivityExtensions.has_entity_type(activity, NotificationTypes.EMAIL_NOTIFICATION)

        assert result is True

    def test_has_entity_type_not_present(self):
        """Test checking for entity type that is not present."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        result = ActivityExtensions.has_entity_type(activity, NotificationTypes.WPX_COMMENT)

        assert result is False

    def test_has_entity_type_case_insensitive(self):
        """Test that entity type checking is case-insensitive."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        result = ActivityExtensions.has_entity_type(activity, "EMAILNOTIFICATION")

        assert result is True

    def test_has_entity_type_no_entities(self):
        """Test checking for entity type in activity with no entities."""
        activity = Activity(type="message")

        result = ActivityExtensions.has_entity_type(activity, NotificationTypes.EMAIL_NOTIFICATION)

        assert result is False

    def test_is_email_notification_true(self):
        """Test checking if activity is an email notification (true case)."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        assert ActivityExtensions.is_email_notification(activity) is True

    def test_is_email_notification_false(self):
        """Test checking if activity is an email notification (false case)."""
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[wpx])

        assert ActivityExtensions.is_email_notification(activity) is False

    def test_is_wpx_comment_notification_true(self):
        """Test checking if activity is a WPX comment notification (true case)."""
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[wpx])

        assert ActivityExtensions.is_wpx_comment_notification(activity) is True

    def test_is_wpx_comment_notification_false(self):
        """Test checking if activity is a WPX comment notification (false case)."""
        email_ref = EmailReference(id="test-email")
        activity = Activity(type="message", entities=[email_ref])

        assert ActivityExtensions.is_wpx_comment_notification(activity) is False

    def test_add_entity_to_activity(self):
        """Test adding an entity to an activity."""
        activity = Activity(type="message")
        email_ref = EmailReference(id="test-email")

        result = ActivityExtensions.add_entity(activity, email_ref)

        assert result is activity  # Should return the same activity for chaining
        assert activity.entities is not None
        assert len(activity.entities) == 1
        assert activity.entities[0] == email_ref

    def test_add_entity_to_activity_with_existing_entities(self):
        """Test adding an entity to an activity that already has entities."""
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[wpx])
        email_ref = EmailReference(id="test-email")

        result = ActivityExtensions.add_entity(activity, email_ref)

        assert result is activity
        assert len(activity.entities) == 2
        assert activity.entities[0] == wpx
        assert activity.entities[1] == email_ref

    def test_clear_entities(self):
        """Test clearing all entities from an activity."""
        email_ref = EmailReference(id="test-email")
        wpx = WpxComment(comment_id="comment-1")
        activity = Activity(type="message", entities=[email_ref, wpx])

        result = ActivityExtensions.clear_entities(activity)

        assert result is activity  # Should return the same activity for chaining
        assert activity.entities is not None
        assert len(activity.entities) == 0

    def test_clear_entities_already_empty(self):
        """Test clearing entities from an activity with no entities."""
        activity = Activity(type="message")

        result = ActivityExtensions.clear_entities(activity)

        assert result is activity
        assert activity.entities is not None
        assert len(activity.entities) == 0

    def test_method_chaining(self):
        """Test that methods support chaining."""
        activity = Activity(type="message")
        email_ref = EmailReference(id="test-email")
        wpx = WpxComment(comment_id="comment-1")

        result = ActivityExtensions.add_entity(
            ActivityExtensions.add_entity(activity, email_ref), wpx
        )

        assert result is activity
        assert len(activity.entities) == 2

    def test_integration_with_existing_email_response_method(self):
        """Test that ActivityExtensions works with existing EmailResponse.create_email_response_activity."""
        # Use the existing static method from EmailResponse
        activity = EmailResponse.create_email_response_activity("<p>Test response</p>")

        # Verify we can extract the entity using ActivityExtensions
        email_response = ActivityExtensions.get_email_response(activity)

        assert email_response is not None
        assert email_response.html_body == "<p>Test response</p>"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

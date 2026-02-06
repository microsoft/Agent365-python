# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal

from microsoft_agents.activity.activity import Activity
from microsoft_agents.activity.entity import Entity


class EmailResponse(Entity):
    """Entity representing an email response to be sent by an agent.

    This class encapsulates the HTML content that will be sent as a response to an
    email notification. It is used to construct reply messages in Outlook scenarios.

    Attributes:
        type: The entity type identifier, always set to "emailResponse".
        html_body: The HTML content of the email response body. Defaults to empty string.
    """

    type: Literal["emailResponse"] = "emailResponse"
    html_body: str = ""

    @staticmethod
    def create_email_response_activity(email_response_html_body: str) -> Activity:
        """Create a new Activity with an EmailResponse entity.

        This factory method constructs a message activity containing an EmailResponse
        entity, which can be sent back to respond to an email notification.

        Args:
            email_response_html_body: The HTML content for the email response body.

        Returns:
            A new Activity instance with type set to 'message' and the EmailResponse
            entity attached to its entities list.

        Example:
            ```python
            activity = EmailResponse.create_email_response_activity(
                "<p>Thank you for your email. I'll get back to you soon.</p>"
            )
            await context.send_activity(activity)
            ```
        """
        working_activity = Activity(type="message")
        email_response = EmailResponse(html_body=email_response_html_body)
        if working_activity.entities is None:
            working_activity.entities = []
        working_activity.entities.append(email_response)
        return working_activity

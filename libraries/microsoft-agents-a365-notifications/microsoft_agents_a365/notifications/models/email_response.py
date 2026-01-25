# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal
from microsoft_agents.activity.activity import Activity
from microsoft_agents.activity.entity import Entity


class EmailResponse(Entity):
    type: Literal["emailResponse"] = "emailResponse"
    html_body: str = ""

    @staticmethod
    def create_email_response_activity(email_response_html_body: str) -> Activity:
        """Create a new Activity with an EmailResponse entity.

        Args:
            email_response_html_body: The HTML content for the email response.

        Returns:
            A new Activity instance with type='message' and the EmailResponse entity attached.
        """
        working_activity = Activity(type="message")
        email_response = EmailResponse(html_body=email_response_html_body)
        if working_activity.entities is None:
            working_activity.entities = []
        working_activity.entities.append(email_response)
        return working_activity

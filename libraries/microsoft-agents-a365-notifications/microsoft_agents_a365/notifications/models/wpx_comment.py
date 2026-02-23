# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal
from microsoft_agents.activity.entity import Entity
from .notification_types import NotificationTypes


class WpxComment(Entity):
    """Entity representing a comment notification from Word, PowerPoint, or Excel.

    This class encapsulates information about a comment made in a Microsoft Office
    document (Word, PowerPoint, or Excel), including the document context and
    comment hierarchy.

    Attributes:
        type: The notification type identifier, always set to "wpxComment".
        odata_id: The OData identifier for the comment resource.
        document_id: The unique identifier of the document containing the comment.
        parent_comment_id: The identifier of the parent comment, if this is a reply.
        comment_id: The unique identifier of this comment.
    """

    type: Literal["wpxComment"] = NotificationTypes.WPX_COMMENT

    odata_id: Optional[str] = None
    document_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    comment_id: Optional[str] = None

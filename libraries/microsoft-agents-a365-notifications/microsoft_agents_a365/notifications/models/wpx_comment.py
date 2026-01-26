# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal
from microsoft_agents.activity.entity import Entity
from .notification_types import NotificationTypes


class WpxComment(Entity):
    type: Literal["wpxComment"] = NotificationTypes.WPX_COMMENT

    odata_id: Optional[str] = None
    document_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    comment_id: Optional[str] = None

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Provides constant values used throughout the Tooling components.
"""


class Constants:
    """
    Provides constant values used throughout the Tooling components.
    """

    class Headers:
        """
        Provides constant header values used for authentication.
        """

        #: The header name used for HTTP authorization tokens.
        AUTHORIZATION = "Authorization"

        #: The prefix used for Bearer authentication tokens in HTTP headers.
        BEARER_PREFIX = "Bearer"

        #: The header name for User-Agent information.
        USER_AGENT = "User-Agent"

        #: Header name for sending the agent identifier to MCP platform for logging/analytics.
        AGENT_ID = "x-ms-agentid"

        #: Header name for the channel ID.
        CHANNEL_ID = "x-ms-channel-id"

        #: Header name for the subchannel ID.
        SUBCHANNEL_ID = "x-ms-subchannel-id"

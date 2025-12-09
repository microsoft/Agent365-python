# Copyright (c) Microsoft. All rights reserved.

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

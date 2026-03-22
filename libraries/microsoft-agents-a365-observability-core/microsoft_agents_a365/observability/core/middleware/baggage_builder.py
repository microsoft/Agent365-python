# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Per request baggage builder for OpenTelemetry context propagation.

import logging
from typing import Any

from opentelemetry import baggage, context

from ..constants import (
    CHANNEL_LINK_KEY,
    CHANNEL_NAME_KEY,
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_BLUEPRINT_ID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_EMAIL_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_CALLER_CLIENT_IP_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_CONVERSATION_ITEM_LINK_KEY,
    SERVICE_NAME_KEY,
    SESSION_DESCRIPTION_KEY,
    SESSION_ID_KEY,
    TENANT_ID_KEY,
    USER_EMAIL_KEY,
    USER_ID_KEY,
    USER_NAME_KEY,
)
from ..utils import validate_and_normalize_ip

logger = logging.getLogger(__name__)


class BaggageBuilder:
    """Per request baggage builder.

    This class provides a fluent API for setting baggage values that will be
    propagated in the OpenTelemetry context.

    Example:
        .. code-block:: python

            builder = (BaggageBuilder()
                       .tenant_id("tenant-123")
                       .agent_id("agent-456"))

            with builder.build():
                # Baggage is set in this context
                pass
            # Baggage is restored after exiting the context
    """

    def __init__(self):
        """Initialize the baggage builder."""
        self._pairs: dict[str, str] = {}

    def operation_source(self, value: str | None) -> "BaggageBuilder":
        """Set the operation source baggage value.

        This captures the name of the service using the SDK.

        Args:
            value: The service name (e.g., "my-agent-service", "weather-bot")

        Returns:
            Self for method chaining
        """
        self._set(SERVICE_NAME_KEY, value)
        return self

    def tenant_id(self, value: str | None) -> "BaggageBuilder":
        """Set the tenant ID baggage value.

        Args:
            value: The tenant ID

        Returns:
            Self for method chaining
        """
        self._set(TENANT_ID_KEY, value)
        return self

    def agent_id(self, value: str | None) -> "BaggageBuilder":
        """Set the agent ID baggage value.

        Args:
            value: The agent ID

        Returns:
            Self for method chaining
        """
        self._set(GEN_AI_AGENT_ID_KEY, value)
        return self

    def agent_auid(self, value: str | None) -> "BaggageBuilder":
        """Set the agent AUID baggage value.

        Args:
            value: The agent AUID

        Returns:
            Self for method chaining
        """
        self._set(GEN_AI_AGENT_AUID_KEY, value)
        return self

    def agent_upn(self, value: str | None) -> "BaggageBuilder":
        """Set the agent UPN baggage value.

        Args:
            value: The agent UPN

        Returns:
            Self for method chaining
        """
        self._set(GEN_AI_AGENT_EMAIL_KEY, value)
        return self

    def agent_blueprint_id(self, value: str | None) -> "BaggageBuilder":
        """Set the agent blueprint ID baggage value.

        Args:
            value: The agent blueprint ID

        Returns:
            Self for method chaining
        """
        self._set(GEN_AI_AGENT_BLUEPRINT_ID_KEY, value)
        return self

    def caller_id(self, value: str | None) -> "BaggageBuilder":
        """Set the caller ID baggage value.

        Args:
            value: The caller ID

        Returns:
            Self for method chaining
        """
        self._set(USER_ID_KEY, value)
        return self

    def agent_name(self, value: str | None) -> "BaggageBuilder":
        """Set the agent name baggage value."""
        self._set(GEN_AI_AGENT_NAME_KEY, value)
        return self

    def agent_description(self, value: str | None) -> "BaggageBuilder":
        """Set the agent description baggage value."""
        self._set(GEN_AI_AGENT_DESCRIPTION_KEY, value)
        return self

    def caller_name(self, value: str | None) -> "BaggageBuilder":
        """Set the caller name baggage value."""
        self._set(USER_NAME_KEY, value)
        return self

    def caller_upn(self, value: str | None) -> "BaggageBuilder":
        """Set the caller UPN baggage value."""
        self._set(USER_EMAIL_KEY, value)
        return self

    def caller_client_ip(self, value: str | None) -> "BaggageBuilder":
        """Set the caller client IP baggage value."""
        self._set(GEN_AI_CALLER_CLIENT_IP_KEY, validate_and_normalize_ip(value))
        return self

    def conversation_id(self, value: str | None) -> "BaggageBuilder":
        """Set the conversation ID baggage value."""
        self._set(GEN_AI_CONVERSATION_ID_KEY, value)
        return self

    def conversation_item_link(self, value: str | None) -> "BaggageBuilder":
        """Set the conversation item link baggage value."""
        self._set(GEN_AI_CONVERSATION_ITEM_LINK_KEY, value)
        return self

    def session_id(self, value: str | None) -> "BaggageBuilder":
        """Set the session ID baggage value."""
        self._set(SESSION_ID_KEY, value)
        return self

    def session_description(self, value: str | None) -> "BaggageBuilder":
        """Set the session description baggage value."""
        self._set(SESSION_DESCRIPTION_KEY, value)
        return self

    def channel_name(self, value: str | None) -> "BaggageBuilder":
        """Sets the channel name baggage value (e.g., 'Teams', 'msteams')."""
        self._set(CHANNEL_NAME_KEY, value)
        return self

    def channel_links(self, value: str | None) -> "BaggageBuilder":
        """Sets the channel link baggage value."""
        self._set(CHANNEL_LINK_KEY, value)
        return self

    def set_pairs(self, pairs: Any) -> "BaggageBuilder":
        """
        Accept dict or iterable of (k,v).
        """
        if not pairs:
            return self
        if isinstance(pairs, dict):
            iterator = pairs.items()
        else:
            iterator = pairs
        for k, v in iterator:
            if v is None:
                continue
            self._set(str(k), str(v))
        return self

    def build(self) -> "BaggageScope":
        """Apply the collected baggage to the current context.

        Returns:
            A context manager that restores the previous baggage on exit
        """
        return BaggageScope(self._pairs)

    def _set(self, key: str, value: str | None) -> None:
        """Add a baggage key/value if the value is not None or whitespace.

        Args:
            key: The baggage key
            value: The baggage value
        """
        if value is not None and value.strip():
            self._pairs[key] = value


class BaggageScope:
    """Context manager for baggage scope.

    This class manages the lifecycle of baggage values, setting them on enter
    and restoring the previous context on exit.
    """

    def __init__(self, pairs: dict[str, str]):
        """Initialize the baggage scope.

        Args:
            pairs: Dictionary of baggage key-value pairs to set
        """
        self._pairs = pairs
        self._previous_context: Any = None
        self._token: Any = None

    def __enter__(self) -> "BaggageScope":
        """Enter the context and set baggage values.

        Returns:
            Self
        """
        # Get the current context
        self._previous_context = context.get_current()

        # Set all baggage values in the new context
        new_context = self._previous_context
        for key, value in self._pairs.items():
            if value and value.strip():
                new_context = baggage.set_baggage(key, value, context=new_context)

        # Attach the new context
        self._token = context.attach(new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore previous baggage.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        # Detach and restore previous context
        if self._token is not None:
            context.detach(self._token)

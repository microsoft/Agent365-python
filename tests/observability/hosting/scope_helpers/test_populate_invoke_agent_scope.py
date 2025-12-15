# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from unittest.mock import MagicMock

import pytest
from microsoft_agents.activity import Activity, ChannelAccount, ConversationAccount
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
)
from microsoft_agents_a365.observability.core.invoke_agent_details import InvokeAgentDetails
from microsoft_agents_a365.observability.core.invoke_agent_scope import InvokeAgentScope
from microsoft_agents_a365.observability.core.tenant_details import TenantDetails
from microsoft_agents_a365.observability.hosting.scope_helpers.populate_invoke_agent_scope import (
    populate,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


@pytest.fixture(autouse=True)
def enable_telemetry():
    """Enable telemetry and set up tracer provider for all tests in this module."""
    # Set environment variable to enable telemetry
    os.environ["ENABLE_OBSERVABILITY"] = "true"

    # Set up a proper tracer provider
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    yield

    # Clean up
    os.environ.pop("ENABLE_OBSERVABILITY", None)


def test_populate():
    """Test populate populates scope from turn context."""
    # Create real InvokeAgentScope with minimal required parameters
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    # Create real Activity and TurnContext
    activity = Activity(
        type="message",
        from_property=ChannelAccount(id="caller-id", aad_object_id="caller-aad-id", name="Caller"),
        recipient=ChannelAccount(id="agent-id", agentic_app_id="agent-app-id", name="Agent"),
        conversation=ConversationAccount(id="conv-123"),
        text="Test message",
        channel_id="test-channel",
        service_url="https://example.com",
    )
    adapter = MagicMock()
    turn_context = TurnContext(adapter, activity)

    result = populate(scope, turn_context)

    # Verify function completes without error and returns the scope
    assert result == scope

    # Verify attributes were set on the span
    assert scope._span is not None
    attributes = scope._span._attributes

    # Check caller attributes
    assert GEN_AI_CALLER_ID_KEY in attributes
    assert attributes[GEN_AI_CALLER_ID_KEY] == "caller-aad-id"

    # Check execution type
    assert GEN_AI_EXECUTION_TYPE_KEY in attributes

    # Check execution source
    assert GEN_AI_EXECUTION_SOURCE_NAME_KEY in attributes
    assert attributes[GEN_AI_EXECUTION_SOURCE_NAME_KEY] == "test-channel"

    # Check conversation ID
    assert GEN_AI_CONVERSATION_ID_KEY in attributes
    assert attributes[GEN_AI_CONVERSATION_ID_KEY] == "conv-123"

    # Check input messages
    assert GEN_AI_INPUT_MESSAGES_KEY in attributes
    assert "Test message" in attributes[GEN_AI_INPUT_MESSAGES_KEY]

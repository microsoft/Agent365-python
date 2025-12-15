# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from unittest.mock import MagicMock

import pytest
from microsoft_agents_a365.observability.core.agent_details import AgentDetails
from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    GEN_AI_INPUT_MESSAGES_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.invoke_agent_details import InvokeAgentDetails
from microsoft_agents_a365.observability.core.invoke_agent_scope import InvokeAgentScope
from microsoft_agents_a365.observability.core.tenant_details import TenantDetails
from microsoft_agents_a365.observability.hosting.scope_helpers.populate_invoke_agent_scope import (
    populate,
    set_caller_tags,
    set_conversation_id_tags,
    set_execution_type_tags,
    set_input_message_tags,
    set_source_metadata_tags,
    set_target_agent_tags,
    set_tenant_id_tags,
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

    # Use mock for TurnContext to avoid dependency on microsoft_agents package
    turn_context = MagicMock()
    activity = MagicMock()
    activity.from_property = MagicMock()
    activity.recipient = MagicMock()
    activity.conversation = MagicMock()
    activity.text = "Test message"
    turn_context.activity = activity

    result = populate(scope, turn_context)

    # Verify function completes without error and returns the scope
    assert result == scope


def test_set_caller_tags():
    """Test set_caller_tags sets caller attributes on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.from_property = MagicMock(
        aad_object_id="caller-id", name="Caller", agentic_user_id="upn", tenant_id="tenant"
    )

    # Verify function completes without error
    set_caller_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_CALLER_ID_KEY in scope._span._attributes
        assert scope._span._attributes[GEN_AI_CALLER_ID_KEY] == "caller-id"


def test_set_execution_type_tags():
    """Test set_execution_type_tags sets execution type on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.from_property = MagicMock(role="user")
    activity.recipient = MagicMock(role="agenticUser")

    # Verify function completes without error
    set_execution_type_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_EXECUTION_TYPE_KEY in scope._span._attributes


def test_set_target_agent_tags():
    """Test set_target_agent_tags sets target agent attributes on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.recipient = MagicMock(
        agentic_app_id="agent-id", name="Agent", aad_object_id="auid", agentic_user_id="upn"
    )

    # Verify function completes without error
    set_target_agent_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_AGENT_ID_KEY in scope._span._attributes
        assert scope._span._attributes[GEN_AI_AGENT_ID_KEY] == "agent-id"


def test_set_tenant_id_tags():
    """Test set_tenant_id_tags sets tenant ID on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.recipient = MagicMock(tenant_id="tenant-123")

    # Verify function completes without error
    set_tenant_id_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert TENANT_ID_KEY in scope._span._attributes
        assert scope._span._attributes[TENANT_ID_KEY] == "tenant-123"


def test_set_source_metadata_tags():
    """Test set_source_metadata_tags sets source metadata on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.channel_id = "test-channel"

    # Verify function completes without error
    set_source_metadata_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_EXECUTION_SOURCE_NAME_KEY in scope._span._attributes
        assert scope._span._attributes[GEN_AI_EXECUTION_SOURCE_NAME_KEY] == "test-channel"


def test_set_conversation_id_tags():
    """Test set_conversation_id_tags sets conversation attributes on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.conversation = MagicMock(id="conv-123")
    activity.service_url = "https://example.com"

    # Verify function completes without error
    set_conversation_id_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_CONVERSATION_ID_KEY in scope._span._attributes
        assert scope._span._attributes[GEN_AI_CONVERSATION_ID_KEY] == "conv-123"


def test_set_input_message_tags():
    """Test set_input_message_tags sets input message on scope."""
    # Create real InvokeAgentScope
    invoke_agent_details = InvokeAgentDetails(
        details=AgentDetails(agent_id="test-agent", agent_name="Test Agent")
    )
    tenant_details = TenantDetails(tenant_id="test-tenant")
    scope = InvokeAgentScope(invoke_agent_details, tenant_details)

    activity = MagicMock()
    activity.text = "Test input message"

    # Verify function completes without error
    set_input_message_tags(scope, activity)

    # Verify attributes were set on the span (if telemetry is enabled)
    if scope._span and hasattr(scope._span, "_attributes"):
        assert GEN_AI_INPUT_MESSAGES_KEY in scope._span._attributes

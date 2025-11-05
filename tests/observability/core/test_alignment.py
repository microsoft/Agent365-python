# Copyright (c) Microsoft. All rights reserved.


import os
import sys
from urllib.parse import urlparse


def test_new_classes():
    """Test the new classes align with .NET SDK."""
    from microsoft_agents_a365.observability.core import (
        AgentDetails,
        ExecutionType,
        InvokeAgentDetails,
        Request,
        SourceMetadata,
        TenantDetails,
    )

    print("✅ Testing new classes...")

    # Test TenantDetails
    tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
    assert tenant_details.tenant_id == "12345678-1234-5678-1234-567812345678"
    print("   ✅ TenantDetails works")

    # Test AgentDetails with icon_uri
    agent_details = AgentDetails(
        agent_id="test-agent-123",
        agent_name="Test Agent",
        agent_description="A test agent",
        conversation_id="conv-456",
        icon_uri="https://example.com/icon.png",
    )
    assert agent_details.agent_id == "test-agent-123"
    assert agent_details.icon_uri == "https://example.com/icon.png"
    print("   ✅ AgentDetails with icon_uri works")

    # Test SourceMetadata
    source_metadata = SourceMetadata(
        id="source-123",
        name="Source Agent",
        icon_uri="https://example.com/source-icon.png",
        description="Source agent description",
    )
    assert source_metadata.id == "source-123"
    print("   ✅ SourceMetadata works")

    # Test ExecutionType
    exec_type = ExecutionType.AGENT_TO_AGENT
    assert exec_type.value == "Agent2Agent"
    print("   ✅ ExecutionType works")

    # Test Request
    request = Request(
        content="Test request content",
        execution_type=ExecutionType.EVENT_TO_AGENT,
        session_id="session-789",
        source_metadata=source_metadata,
        payload="Test payload",
    )
    assert request.content == "Test request content"
    assert request.session_id == "session-789"
    print("   ✅ Request works")

    # Test InvokeAgentDetails with session_id
    invoke_details = InvokeAgentDetails(
        endpoint=urlparse("https://example.com:8080/agent"),
        details=agent_details,
        session_id="session-789",
    )
    assert invoke_details.session_id == "session-789"
    assert invoke_details.details.agent_id == "test-agent-123"
    print("   ✅ InvokeAgentDetails with session_id works")


def test_scope_functionality():
    """Test that scopes work with new parameters."""

    os.environ["ENABLE_OBSERVABILITY"] = "true"

    from urllib.parse import urlparse

    from microsoft_agents_a365.observability.core import (
        AgentDetails,
        ExecutionType,
        InvokeAgentDetails,
        InvokeAgentScope,
        Request,
        SourceMetadata,
        TenantDetails,
    )

    print("✅ Testing scope functionality...")

    # Create tenant details
    tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")

    # Test scope functionality with Request
    source_metadata = SourceMetadata(
        id="source-agent-456",
        name="Source Agent",
        icon_uri="https://example.com/source.png",
        description="Source agent description",
    )

    request = Request(
        content="Execute agent request",
        execution_type=ExecutionType.AGENT_TO_AGENT,
        session_id="session-123",
        source_metadata=source_metadata,
        payload="Agent execution payload",
    )

    # Test InvokeAgentScope with enhanced details
    agent_details = AgentDetails(
        agent_id="target-agent-789",
        agent_name="Target Agent",
        agent_description="Agent being invoked",
        conversation_id="conv-123",
        icon_uri="https://example.com/target.png",
    )

    invoke_details = InvokeAgentDetails(
        endpoint=urlparse("https://example.com:8080/agent"),
        details=agent_details,
        session_id="session-456",
    )

    with InvokeAgentScope.start(invoke_details, tenant_details, request) as scope:
        assert scope is not None, "Scope should be created when telemetry is enabled"
        print("   ✅ InvokeAgentScope with enhanced details works")


def test_constants_alignment():
    """Test that constants are aligned with .NET SDK."""
    from microsoft_agents_a365.observability.core.constants import (
        AGENT_ID_KEY,
        GEN_AI_EXECUTION_PAYLOAD_KEY,
        GEN_AI_EXECUTION_TYPE_KEY,
        GEN_AI_ICON_URI_KEY,
        SESSION_ID_KEY,
    )

    print("✅ Testing constants alignment...")

    # Key change: agent.id -> gen_ai.agent.id
    assert AGENT_ID_KEY == "gen_ai.agent.id", f"Expected 'gen_ai.agent.id', got '{AGENT_ID_KEY}'"
    print("   ✅ AGENT_ID_KEY is correctly aligned with .NET SDK")

    # New constants from .NET SDK
    assert SESSION_ID_KEY == "session.id"
    assert GEN_AI_ICON_URI_KEY == "gen_ai.agent365.icon_uri"
    assert GEN_AI_EXECUTION_TYPE_KEY == "gen_ai.execution.type"
    assert GEN_AI_EXECUTION_PAYLOAD_KEY == "gen_ai.execution.payload"
    print("   ✅ New constants match .NET SDK")


def test_span_processor():
    """Test that span processor works with updated constants."""
    from microsoft_agents_a365.observability.core import SpanProcessor

    print("✅ Testing span processor...")

    # Create span processor
    processor = SpanProcessor()
    assert processor is not None
    print("   ✅ SpanProcessor created successfully")


def main():
    """Run all tests."""
    print("🔍 Testing Agent365 Python SDK alignment with .NET SDK...\n")

    try:
        test_constants_alignment()
        print()

        test_new_classes()
        print()

        test_scope_functionality()
        print()

        test_span_processor()
        print()

        print("🎉 All tests passed! Python SDK is aligned with .NET SDK.")
        return 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

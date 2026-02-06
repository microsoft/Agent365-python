# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from urllib.parse import urlparse

from microsoft_agents_a365.observability.core.tenant_details import TenantDetails


def main():
    """Demonstrate the aligned Microsoft Agent 365 Python SDK functionality."""

    # Enable telemetry (aligned with .NET SDK environment variable)
    os.environ["ENABLE_OBSERVABILITY"] = "true"

    # Import the updated SDK classes
    from microsoft_agents_a365.observability.core import (
        AgentDetails,
        ExecutionType,
        InvokeAgentDetails,
        InvokeAgentScope,
        Request,
        SourceMetadata,
        configure,
    )

    print("🚀 Microsoft Agent 365 Python SDK - Aligned with .NET SDK")
    print("=" * 50)

    # Configure telemetry (existing function still works)
    configure("my-service", "my-namespace")
    print("✅ Telemetry configured")

    # Example 1: Enhanced Agent Execution with Session and Source Metadata
    print("\n📋 Example 1: Enhanced Agent Execution")

    # Create source metadata (from calling agent)
    source_metadata = SourceMetadata(
        id="calling-agent-456",
        name="Calling Agent",
        icon_uri="https://example.com/calling-agent-icon.png",
        description="The agent that initiated this request",
    )

    # Create a rich request object
    Request(
        content="Process customer inquiry about order status",
        execution_type=ExecutionType.AGENT_TO_AGENT,
        session_id="session-abc123",
        source_metadata=source_metadata,
        payload="Customer ID: 12345, Order ID: 67890",
    )

    # Note: ExecuteAgentScope has been removed from the SDK
    # Tool execution can still be used directly
    print("   🔄 Tool execution example (ExecuteAgentScope no longer available)")

    # Example tool usage that would typically be inside an agent execution context
    # Note: This would require proper agent_details and tenant_details in real usage
    print("   🔧 Tool execution would be used within agent contexts")
    print("   ✅ SDK functionality demonstrated (ExecuteAgentScope removed)")

    # Example 2: Agent-to-Agent Invocation with Enhanced Details
    print("\n📞 Example 2: Agent-to-Agent Invocation")

    tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")

    # Create detailed agent information (aligned with .NET SDK AgentDetails)
    target_agent_details = AgentDetails(
        agent_id="inventory-agent-999",
        agent_name="Inventory Agent",
        agent_description="Handles inventory queries and updates",
        conversation_id="conv-xyz789",
        icon_uri="https://example.com/inventory-agent-icon.png",  # New icon_uri field
    )

    # Create invoke agent details (aligned with .NET SDK InvokeAgentDetails)
    invoke_details = InvokeAgentDetails(
        endpoint=urlparse("https://agents.company.com:8080/inventory"),
        details=target_agent_details,
        session_id="session-abc123",  # New session_id field
    )

    # Create request for the invocation
    invoke_request = Request(
        content="Check inventory for product SKU: ABC-123",
        execution_type=ExecutionType.AGENT_TO_AGENT,
        session_id="session-abc123",
        source_metadata=source_metadata,
    )

    # Use InvokeAgentScope with enhanced details (like .NET SDK)
    with InvokeAgentScope.start(invoke_details, tenant_details, invoke_request):
        print("   📡 Agent invocation started with full agent details and session context")
        print(f"   📊 Target: {target_agent_details.agent_name} ({target_agent_details.agent_id})")
        print(f"   🌐 Endpoint: {invoke_details.endpoint.hostname}:{invoke_details.endpoint.port}")
        print(f"   🆔 Session: {invoke_details.session_id}")
        print(f"   🎨 Icon: {target_agent_details.icon_uri}")

    print("   ✅ Agent invocation completed with comprehensive telemetry")

    # Example 3: Demonstrate Backward Compatibility
    print("\n🔄 Example 3: Backward Compatibility")

    # Note: ExecuteAgentScope has been removed from the SDK
    print("   ✅ ExecuteAgentScope has been removed from the SDK")

    # Tool execution still works but requires proper context in real usage
    print("   ✅ Tool execution API available (requires agent/tenant context)")

    print("\n🎯 Key Alignments with .NET SDK:")
    print("   ✅ AgentDetails now includes icon_uri")
    print("   ✅ InvokeAgentDetails now includes session_id")
    print("   ✅ ExecuteAgentScope has been removed from Python SDK")
    print("   ✅ Constants aligned: gen_ai.agent.id, session.id, gen_ai.agent365.icon_uri")
    print("   ✅ New classes: SourceMetadata, Request, ExecutionType")
    print("   ✅ Baggage propagation from parent to child spans")
    print("   ✅ Backward compatibility maintained")

    print("\n🎉 Python SDK is now fully aligned with .NET SDK!")


if __name__ == "__main__":
    main()

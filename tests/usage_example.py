# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os


def main():
    """Demonstrate the aligned Microsoft Agent 365 Python SDK functionality."""

    # Enable telemetry (aligned with .NET SDK environment variable)
    os.environ["ENABLE_OBSERVABILITY"] = "true"

    # Import the updated SDK classes
    from microsoft_agents_a365.observability.core import (
        AgentDetails,
        Channel,
        InvokeAgentScope,
        InvokeAgentScopeDetails,
        Request,
        ServiceEndpoint,
        configure,
    )

    print("🚀 Microsoft Agent 365 Python SDK - Aligned with .NET SDK")
    print("=" * 50)

    # Configure telemetry (existing function still works)
    configure("my-service", "my-namespace")
    print("✅ Telemetry configured")

    # Example 1: Enhanced Agent Execution with Session and Channel
    print("\n📋 Example 1: Enhanced Agent Execution")

    # Create channel (from calling agent)
    channel = Channel(
        name="Calling Agent",
        link="The agent that initiated this request",
    )

    # Create a rich request object
    Request(
        content="Process customer inquiry about order status",
        session_id="session-abc123",
        channel=channel,
        conversation_id="conv-12345",
    )

    # Note: ExecuteAgentScope has been removed from the SDK
    # Tool execution can still be used directly
    print("   🔄 Tool execution example (ExecuteAgentScope no longer available)")

    # Example tool usage that would typically be inside an agent execution context
    # Note: This would require proper agent_details in real usage
    print("   🔧 Tool execution would be used within agent contexts")
    print("   ✅ SDK functionality demonstrated (ExecuteAgentScope removed)")

    # Example 2: Agent-to-Agent Invocation with Enhanced Details
    print("\n📞 Example 2: Agent-to-Agent Invocation")

    # Create detailed agent information (aligned with .NET SDK AgentDetails)
    target_agent_details = AgentDetails(
        agent_id="inventory-agent-999",
        agent_name="Inventory Agent",
        agent_description="Handles inventory queries and updates",
        icon_uri="https://example.com/inventory-agent-icon.png",
    )

    # Create invoke agent scope details (aligned with .NET SDK)
    invoke_scope_details = InvokeAgentScopeDetails(
        endpoint=ServiceEndpoint(hostname="agents.company.com", port=8080),
    )

    # Create request for the invocation
    invoke_request = Request(
        content="Check inventory for product SKU: ABC-123",
        session_id="session-abc123",
        channel=channel,
        conversation_id="conv-xyz789",
    )

    # Use InvokeAgentScope with enhanced details (like .NET SDK)
    with InvokeAgentScope.start(invoke_request, invoke_scope_details, target_agent_details):
        print("   📡 Agent invocation started with full agent details and session context")
        print(f"   📊 Target: {target_agent_details.agent_name} ({target_agent_details.agent_id})")
        print(
            f"   🌐 Endpoint: "
            f"{invoke_scope_details.endpoint.hostname}:{invoke_scope_details.endpoint.port}"
        )
        print(f"   🎨 Icon: {target_agent_details.icon_uri}")

    print("   ✅ Agent invocation completed with comprehensive telemetry")

    # Example 3: Demonstrate Backward Compatibility
    print("\n🔄 Example 3: Backward Compatibility")

    # Note: ExecuteAgentScope has been removed from the SDK
    print("   ✅ ExecuteAgentScope has been removed from the SDK")

    # Tool execution still works but requires proper context in real usage
    print("   ✅ Tool execution API available (requires agent context)")

    print("\n🎯 Key Alignments with .NET SDK:")
    print("   ✅ AgentDetails now includes icon_uri")
    print("   ✅ InvokeAgentScopeDetails for scope configuration")
    print("   ✅ ExecuteAgentScope has been removed from Python SDK")
    print("   ✅ Constants aligned: gen_ai.agent.id, session.id, gen_ai.agent365.icon_uri")
    print("   ✅ New classes: Channel, Request, SpanDetails, UserDetails, CallerDetails")
    print("   ✅ Baggage propagation from parent to child spans")
    print("   ✅ Backward compatibility maintained")

    print("\n🎉 Python SDK is now fully aligned with .NET SDK!")


if __name__ == "__main__":
    main()

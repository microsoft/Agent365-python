# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    ExecuteToolScope,
    TenantDetails,
    ToolCallDetails,
    configure,
)


class TestExecuteToolScope(unittest.TestCase):
    """Unit tests for ExecuteToolScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Agent365 for testing
        configure(
            service_name="test-execute-tool-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for tool execution testing",
        )
        cls.tool_details = ToolCallDetails(
            tool_name="weather_tool",
            arguments='{"location": "Seattle", "units": "metric"}',
            tool_call_id="call-123",
            description="Get current weather information for a location",
        )

    def test_record_response_method_exists(self):
        """Test that record_response method exists on ExecuteToolScope."""
        scope = ExecuteToolScope.start(self.tool_details, self.agent_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_response"))
            self.assertTrue(callable(scope.record_response))
            scope.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)

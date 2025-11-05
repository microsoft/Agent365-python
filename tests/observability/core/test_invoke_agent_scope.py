# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from urllib.parse import urlparse

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    InvokeAgentDetails,
    InvokeAgentScope,
    TenantDetails,
    configure,
)


class TestInvokeAgentScope(unittest.TestCase):
    """Unit tests for InvokeAgentScope and its methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Configure Agent365 for testing
        configure(
            service_name="test-invoke-agent-service",
            service_namespace="test-namespace",
        )
        # Create test data
        cls.tenant_details = TenantDetails(tenant_id="12345678-1234-5678-1234-567812345678")
        cls.agent_details = AgentDetails(
            agent_id="test-agent-123",
            agent_name="Test Agent",
            agent_description="A test agent for invoke scope testing",
        )
        cls.invoke_details = InvokeAgentDetails(
            endpoint=urlparse("https://example.com/agent"),
            details=cls.agent_details,
            session_id="session-123",
        )

    def test_record_response_method_exists(self):
        """Test that record_response method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_response"))
            self.assertTrue(callable(scope.record_response))
            scope.dispose()

    def test_record_input_messages_method_exists(self):
        """Test that record_input_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_input_messages"))
            self.assertTrue(callable(scope.record_input_messages))
            scope.dispose()

    def test_record_output_messages_method_exists(self):
        """Test that record_output_messages method exists on InvokeAgentScope."""
        scope = InvokeAgentScope.start(self.invoke_details, self.tenant_details)

        if scope is not None:
            # Test that the method exists
            self.assertTrue(hasattr(scope, "record_output_messages"))
            self.assertTrue(callable(scope.record_output_messages))
            scope.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)

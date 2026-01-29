# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for add_tool_servers_to_agent method in McpToolRegistrationService.

These tests verify that httpx.AsyncClient is correctly configured with
Authorization and User-Agent headers, and that MCPStreamableHTTPTool is
instantiated with the http_client parameter (not headers).

This prevents regressions to the bug where passing headers directly to
MCPStreamableHTTPTool via **kwargs was silently ignored, causing 400 Bad Request
errors when calling MCP tool servers.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from microsoft_agents_a365.tooling.extensions.agentframework.services import (
    McpToolRegistrationService,
)
from microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service import (
    MCP_HTTP_CLIENT_TIMEOUT_SECONDS,
)
from microsoft_agents_a365.tooling.utils.constants import Constants


class TestAddToolServersHttpxClientConfiguration:
    """Tests for httpx.AsyncClient configuration in add_tool_servers_to_agent."""

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock TurnContext."""
        mock_context = Mock()
        mock_activity = Mock()
        mock_conversation = Mock()

        mock_conversation.id = "conv-test-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = "msg-test-456"

        mock_context.activity = mock_activity
        return mock_context

    @pytest.fixture
    def mock_auth(self):
        """Create a mock Authorization that returns a token on exchange."""
        mock_auth = AsyncMock()
        mock_token_result = Mock()
        mock_token_result.token = "test-auth-token-12345"
        mock_auth.exchange_token = AsyncMock(return_value=mock_token_result)
        return mock_auth

    @pytest.fixture
    def mock_chat_client(self):
        """Create a mock OpenAIChatClient or AzureOpenAIChatClient."""
        return Mock()

    @pytest.fixture
    def mock_mcp_server_config(self):
        """Create a mock MCP server configuration."""
        config = Mock()
        config.mcp_server_name = "test-mcp-server"
        config.mcp_server_unique_name = "test-mcp-server-unique"
        config.url = "https://test-mcp-server.example.com/api"
        return config

    @pytest.fixture
    def service(self):
        """Create McpToolRegistrationService instance."""
        return McpToolRegistrationService()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_httpx_client_has_authorization_header(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
        mock_mcp_server_config,
    ):
        """Test that httpx.AsyncClient is created with Authorization header."""
        auth_token = "test-bearer-token-xyz"

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_mcp_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_http_client_instance = MagicMock()
            mock_httpx_client.return_value = mock_http_client_instance

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token=auth_token,
            )

            # Verify httpx.AsyncClient was called with headers containing Authorization
            mock_httpx_client.assert_called_once()
            call_kwargs = mock_httpx_client.call_args[1]

            assert "headers" in call_kwargs
            expected_auth_header = f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
            assert call_kwargs["headers"][Constants.Headers.AUTHORIZATION] == expected_auth_header

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_httpx_client_has_user_agent_header(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
        mock_mcp_server_config,
    ):
        """Test that httpx.AsyncClient is created with User-Agent header."""
        auth_token = "test-bearer-token-xyz"
        expected_user_agent = "AgentFramework/1.0"

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_mcp_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value=expected_user_agent,
            ),
        ):
            mock_http_client_instance = MagicMock()
            mock_httpx_client.return_value = mock_http_client_instance

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token=auth_token,
            )

            # Verify httpx.AsyncClient was called with User-Agent header
            mock_httpx_client.assert_called_once()
            call_kwargs = mock_httpx_client.call_args[1]

            assert "headers" in call_kwargs
            assert call_kwargs["headers"][Constants.Headers.USER_AGENT] == expected_user_agent

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_httpx_client_has_correct_timeout(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
        mock_mcp_server_config,
    ):
        """Test that httpx.AsyncClient is created with the defined timeout constant."""
        auth_token = "test-bearer-token-xyz"

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_mcp_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_http_client_instance = MagicMock()
            mock_httpx_client.return_value = mock_http_client_instance

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token=auth_token,
            )

            # Verify httpx.AsyncClient was called with correct timeout
            mock_httpx_client.assert_called_once()
            call_kwargs = mock_httpx_client.call_args[1]

            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == MCP_HTTP_CLIENT_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mcp_tool_receives_http_client_not_headers(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
        mock_mcp_server_config,
    ):
        """Test that MCPStreamableHTTPTool is instantiated with http_client parameter.

        This is the critical test that prevents regression to the bug where
        headers were passed directly to MCPStreamableHTTPTool and silently ignored.
        The fix passes an httpx.AsyncClient with pre-configured headers instead.
        """
        auth_token = "test-bearer-token-xyz"

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_mcp_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ) as mock_mcp_tool,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_http_client_instance = MagicMock()
            mock_httpx_client.return_value = mock_http_client_instance

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token=auth_token,
            )

            # Verify MCPStreamableHTTPTool was called with http_client, NOT headers
            mock_mcp_tool.assert_called_once()
            call_kwargs = mock_mcp_tool.call_args[1]

            # Critical: http_client must be passed (this is the fix)
            assert "http_client" in call_kwargs
            assert call_kwargs["http_client"] is mock_http_client_instance

            # Critical: headers must NOT be passed directly (this was the bug)
            assert "headers" not in call_kwargs

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_httpx_client_added_to_internal_list_for_cleanup(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
        mock_mcp_server_config,
    ):
        """Test that created httpx clients are tracked in _http_clients for cleanup."""
        auth_token = "test-bearer-token-xyz"

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_mcp_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_http_client_instance = MagicMock()
            mock_httpx_client.return_value = mock_http_client_instance

            # Clear any pre-existing clients
            service._http_clients.clear()

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token=auth_token,
            )

            # Verify httpx client was added to internal tracking list
            assert len(service._http_clients) == 1
            assert service._http_clients[0] is mock_http_client_instance


class TestMcpToolRegistrationServiceCleanup:
    """Tests for cleanup method to ensure httpx clients are properly closed."""

    @pytest.fixture
    def service(self):
        """Create McpToolRegistrationService instance."""
        return McpToolRegistrationService()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_closes_all_httpx_clients(self, service):
        """Test that cleanup properly closes all tracked httpx clients."""
        # Create mock httpx clients
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()

        service._http_clients = [mock_client1, mock_client2]

        await service.cleanup()

        # Verify both clients had aclose() called
        mock_client1.aclose.assert_called_once()
        mock_client2.aclose.assert_called_once()

        # Verify the list was cleared
        assert len(service._http_clients) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_handles_client_close_errors_gracefully(self, service):
        """Test that cleanup continues even if a client close raises an exception."""
        # Create mock clients - first one raises, second should still be closed
        mock_client1 = AsyncMock()
        mock_client1.aclose.side_effect = Exception("Connection error")
        mock_client2 = AsyncMock()

        service._http_clients = [mock_client1, mock_client2]

        # Should not raise
        await service.cleanup()

        # Both clients should have had aclose attempted
        mock_client1.aclose.assert_called_once()
        mock_client2.aclose.assert_called_once()

        # List should be cleared even after errors
        assert len(service._http_clients) == 0


class TestHttpxClientLifecycle:
    """End-to-end tests for httpx client lifecycle management.

    These tests verify that clients created during add_tool_servers_to_agent()
    are properly tracked and cleaned up by cleanup(), preventing connection
    and file descriptor leaks.
    """

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock TurnContext."""
        mock_context = Mock()
        mock_activity = Mock()
        mock_conversation = Mock()

        mock_conversation.id = "conv-test-123"
        mock_activity.conversation = mock_conversation
        mock_activity.id = "msg-test-456"

        mock_context.activity = mock_activity
        return mock_context

    @pytest.fixture
    def mock_auth(self):
        """Create a mock Authorization that returns a token on exchange."""
        mock_auth = AsyncMock()
        mock_token_result = Mock()
        mock_token_result.token = "test-auth-token-12345"
        mock_auth.exchange_token = AsyncMock(return_value=mock_token_result)
        return mock_auth

    @pytest.fixture
    def mock_chat_client(self):
        """Create a mock chat client."""
        return Mock()

    @pytest.fixture
    def service(self):
        """Create McpToolRegistrationService instance."""
        return McpToolRegistrationService()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_full_client_lifecycle_single_server(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
    ):
        """Test full lifecycle: create client via add_tool_servers, then cleanup.

        This end-to-end test ensures that:
        1. add_tool_servers_to_agent() creates and tracks httpx clients
        2. cleanup() calls aclose() on each tracked client
        3. cleanup() clears the tracking list
        """
        mock_server_config = Mock()
        mock_server_config.mcp_server_name = "test-server"
        mock_server_config.mcp_server_unique_name = "test-server-unique"
        mock_server_config.url = "https://test.example.com/api"

        mock_http_client_instance = MagicMock()

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_httpx_client.return_value = mock_http_client_instance

            # Step 1: Create agent with tool servers - this should create and track httpx client
            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token="test-token",
            )

            # Verify client was tracked
            assert len(service._http_clients) == 1
            assert service._http_clients[0] is mock_http_client_instance

            # Step 2: Call cleanup - this should close the client
            await service.cleanup()

            # Verify aclose() was called on the client created during add_tool_servers
            mock_http_client_instance.aclose.assert_called_once()

            # Verify tracking list was cleared
            assert len(service._http_clients) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_full_client_lifecycle_multiple_servers(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
    ):
        """Test lifecycle with multiple MCP servers creating multiple clients.

        Verifies that when multiple tool servers are configured, each gets its
        own httpx client that is properly tracked and cleaned up.
        """
        mock_server_config1 = Mock()
        mock_server_config1.mcp_server_name = "server-1"
        mock_server_config1.mcp_server_unique_name = "server-1-unique"
        mock_server_config1.url = "https://server1.example.com/api"

        mock_server_config2 = Mock()
        mock_server_config2.mcp_server_name = "server-2"
        mock_server_config2.mcp_server_unique_name = "server-2-unique"
        mock_server_config2.url = "https://server2.example.com/api"

        mock_server_config3 = Mock()
        mock_server_config3.mcp_server_name = "server-3"
        mock_server_config3.mcp_server_unique_name = "server-3-unique"
        mock_server_config3.url = "https://server3.example.com/api"

        # Create unique mock clients for each server
        mock_clients = [MagicMock() for _ in range(3)]
        client_iter = iter(mock_clients)

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_server_config1, mock_server_config2, mock_server_config3],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            # Return a different mock client for each call
            mock_httpx_client.side_effect = lambda **kwargs: next(client_iter)

            # Step 1: Create agent with multiple tool servers
            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token="test-token",
            )

            # Verify all 3 clients were tracked
            assert len(service._http_clients) == 3
            for i, client in enumerate(mock_clients):
                assert service._http_clients[i] is client

            # Step 2: Call cleanup
            await service.cleanup()

            # Verify aclose() was called on ALL clients
            for client in mock_clients:
                client.aclose.assert_called_once()

            # Verify tracking list was cleared
            assert len(service._http_clients) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_idempotent_no_clients(self, service):
        """Test that cleanup() is safe to call when no clients exist.

        Ensures cleanup doesn't raise errors when called on a fresh service
        or called multiple times.
        """
        # Verify initial state is empty
        assert len(service._http_clients) == 0

        # Should not raise when no clients to clean up
        await service.cleanup()

        # Still empty
        assert len(service._http_clients) == 0

        # Safe to call again
        await service.cleanup()
        assert len(service._http_clients) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_called_twice_after_creating_clients(
        self,
        service,
        mock_turn_context,
        mock_auth,
        mock_chat_client,
    ):
        """Test that calling cleanup() twice doesn't cause issues.

        After the first cleanup, the list is cleared, so the second cleanup
        should be a no-op without errors.
        """
        mock_server_config = Mock()
        mock_server_config.mcp_server_name = "test-server"
        mock_server_config.mcp_server_unique_name = "test-server-unique"
        mock_server_config.url = "https://test.example.com/api"

        mock_http_client_instance = MagicMock()

        with (
            patch.object(
                service._mcp_server_configuration_service,
                "list_tool_servers",
                new_callable=AsyncMock,
                return_value=[mock_server_config],
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.httpx.AsyncClient"
            ) as mock_httpx_client,
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.MCPStreamableHTTPTool"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.ChatAgent"
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.resolve_agent_identity",
                return_value="test-agent-id",
            ),
            patch(
                "microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service.Utility.get_user_agent_header",
                return_value="TestAgent/1.0",
            ),
        ):
            mock_httpx_client.return_value = mock_http_client_instance

            await service.add_tool_servers_to_agent(
                chat_client=mock_chat_client,
                agent_instructions="Test instructions",
                initial_tools=[],
                auth=mock_auth,
                auth_handler_name="test-auth-handler",
                turn_context=mock_turn_context,
                auth_token="test-token",
            )

            # First cleanup
            await service.cleanup()
            mock_http_client_instance.aclose.assert_called_once()
            assert len(service._http_clients) == 0

            # Second cleanup should be safe (no-op)
            await service.cleanup()
            # aclose still only called once (not twice)
            mock_http_client_instance.aclose.assert_called_once()
            assert len(service._http_clients) == 0


class TestMcpHttpClientTimeoutConstant:
    """Tests for the MCP_HTTP_CLIENT_TIMEOUT_SECONDS constant."""

    @pytest.mark.unit
    def test_timeout_constant_is_90_seconds(self):
        """Verify the timeout constant has the expected value."""
        assert MCP_HTTP_CLIENT_TIMEOUT_SECONDS == 90.0

    @pytest.mark.unit
    def test_timeout_constant_is_float(self):
        """Verify the timeout constant is a float for httpx compatibility."""
        assert isinstance(MCP_HTTP_CLIENT_TIMEOUT_SECONDS, float)

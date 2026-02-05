# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for McpToolRegistrationService in Google ADK extension."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMcpToolRegistrationServiceInit:
    """Tests for McpToolRegistrationService initialization."""

    @pytest.mark.unit
    def test_init_default_logger(self):
        """Test initialization with default logger."""
        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            assert service._logger is not None
            assert service.config_service is not None
            assert service._connected_servers == []

    @pytest.mark.unit
    def test_init_custom_logger(self):
        """Test initialization with custom logger."""
        import logging

        custom_logger = logging.getLogger("custom_test_logger")

        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService(logger=custom_logger)

            assert service._logger is custom_logger

    @pytest.mark.unit
    def test_orchestrator_name(self):
        """Test that orchestrator name is set correctly."""
        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            assert McpToolRegistrationService._orchestrator_name == "GoogleADK"


class TestAddToolServersToAgent:
    """Tests for add_tool_servers_to_agent method."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock Google ADK Agent."""
        mock = MagicMock()
        mock.name = "test-agent"
        mock.model = "gemini-pro"
        mock.description = "A test agent"
        mock.tools = []
        return mock

    @pytest.fixture
    def mock_authorization(self):
        """Create a mock Authorization object."""
        mock = AsyncMock()
        mock_token = MagicMock()
        mock_token.token = "test-token-123"
        mock.exchange_token = AsyncMock(return_value=mock_token)
        return mock

    @pytest.fixture
    def mock_turn_context(self):
        """Create a mock TurnContext."""
        mock = MagicMock()
        mock_activity = MagicMock()
        mock_conversation = MagicMock()
        mock_conversation.id = "conv-123"
        mock_activity.conversation = mock_conversation
        mock.activity = mock_activity
        return mock

    @pytest.fixture
    def mock_server_config(self):
        """Create a mock MCP server configuration."""
        mock = MagicMock()
        mock.mcp_server_name = "test-server"
        mock.mcp_server_unique_name = "https://test-server.example.com/mcp"
        return mock

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_add_tool_servers_exchanges_token_when_not_provided(
        self, mock_agent, mock_authorization, mock_turn_context
    ):
        """Test that token is exchanged when not provided."""
        with (
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
            ) as mock_config_service_class,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Utility"
            ) as mock_utility,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.get_mcp_platform_authentication_scope"
            ) as mock_get_scope,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Agent"
            ) as mock_agent_class,
        ):
            # Setup mocks
            mock_get_scope.return_value = ["https://test.scope/.default"]
            mock_utility.resolve_agent_identity.return_value = "agent-123"
            mock_utility.get_user_agent_header.return_value = "Agent365SDK/1.0"

            mock_config_service = AsyncMock()
            mock_config_service.list_tool_servers = AsyncMock(return_value=[])
            mock_config_service_class.return_value = mock_config_service

            mock_agent_class.return_value = mock_agent

            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Act
            await service.add_tool_servers_to_agent(
                agent=mock_agent,
                auth=mock_authorization,
                auth_handler_name="graph",
                context=mock_turn_context,
            )

            # Assert
            mock_authorization.exchange_token.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_add_tool_servers_uses_provided_token(
        self, mock_agent, mock_authorization, mock_turn_context
    ):
        """Test that provided token is used instead of exchanging."""
        with (
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
            ) as mock_config_service_class,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Utility"
            ) as mock_utility,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Agent"
            ) as mock_agent_class,
        ):
            # Setup mocks
            mock_utility.resolve_agent_identity.return_value = "agent-123"
            mock_utility.get_user_agent_header.return_value = "Agent365SDK/1.0"

            mock_config_service = AsyncMock()
            mock_config_service.list_tool_servers = AsyncMock(return_value=[])
            mock_config_service_class.return_value = mock_config_service

            mock_agent_class.return_value = mock_agent

            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Act
            await service.add_tool_servers_to_agent(
                agent=mock_agent,
                auth=mock_authorization,
                auth_handler_name="graph",
                context=mock_turn_context,
                auth_token="pre-existing-token",
            )

            # Assert - exchange_token should NOT be called
            mock_authorization.exchange_token.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_add_tool_servers_creates_mcp_toolsets(
        self, mock_agent, mock_authorization, mock_turn_context, mock_server_config
    ):
        """Test that MCP toolsets are created for each server config."""
        with (
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
            ) as mock_config_service_class,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Utility"
            ) as mock_utility,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolset"
            ) as mock_toolset_class,
        ):
            # Setup mocks
            mock_utility.resolve_agent_identity.return_value = "agent-123"
            mock_utility.get_user_agent_header.return_value = "Agent365SDK/1.0"

            mock_config_service = AsyncMock()
            mock_config_service.list_tool_servers = AsyncMock(return_value=[mock_server_config])
            mock_config_service_class.return_value = mock_config_service

            mock_toolset = MagicMock()
            mock_toolset_class.return_value = mock_toolset

            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Set up existing tools on the agent
            existing_tool = MagicMock()
            mock_agent.tools = [existing_tool]

            # Act
            await service.add_tool_servers_to_agent(
                agent=mock_agent,
                auth=mock_authorization,
                auth_handler_name="graph",
                context=mock_turn_context,
                auth_token="test-token",
            )

            # Assert
            mock_toolset_class.assert_called_once()
            assert mock_toolset in service._connected_servers
            # Verify agent tools were updated in place with both existing and new tools
            assert existing_tool in mock_agent.tools
            assert mock_toolset in mock_agent.tools

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_add_tool_servers_modifies_agent_in_place(
        self, mock_agent, mock_authorization, mock_turn_context
    ):
        """Test that the agent is modified in place and method returns None."""
        with (
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
            ) as mock_config_service_class,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Utility"
            ) as mock_utility,
        ):
            # Setup mocks
            mock_utility.resolve_agent_identity.return_value = "agent-123"
            mock_utility.get_user_agent_header.return_value = "Agent365SDK/1.0"

            mock_config_service = AsyncMock()
            mock_config_service.list_tool_servers = AsyncMock(return_value=[])
            mock_config_service_class.return_value = mock_config_service

            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Set up existing tools on the agent
            existing_tool = MagicMock()
            mock_agent.tools = [existing_tool]

            # Act
            result = await service.add_tool_servers_to_agent(
                agent=mock_agent,
                auth=mock_authorization,
                auth_handler_name="graph",
                context=mock_turn_context,
                auth_token="test-token",
            )

            # Assert - method returns None and modifies agent in place
            assert result is None
            assert existing_tool in mock_agent.tools

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_add_tool_servers_handles_toolset_creation_error(
        self, mock_agent, mock_authorization, mock_turn_context, mock_server_config
    ):
        """Test that errors during toolset creation are handled gracefully."""
        with (
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
            ) as mock_config_service_class,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.Utility"
            ) as mock_utility,
            patch(
                "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolset"
            ) as mock_toolset_class,
        ):
            # Setup mocks
            mock_utility.resolve_agent_identity.return_value = "agent-123"
            mock_utility.get_user_agent_header.return_value = "Agent365SDK/1.0"

            mock_config_service = AsyncMock()
            mock_config_service.list_tool_servers = AsyncMock(return_value=[mock_server_config])
            mock_config_service_class.return_value = mock_config_service

            # Make toolset creation fail
            mock_toolset_class.side_effect = Exception("Connection failed")

            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Set up existing tools on the agent
            existing_tool = MagicMock()
            mock_agent.tools = [existing_tool]

            # Act - should not raise
            result = await service.add_tool_servers_to_agent(
                agent=mock_agent,
                auth=mock_authorization,
                auth_handler_name="graph",
                context=mock_turn_context,
                auth_token="test-token",
            )

            # Assert - returns None, agent modified in place, no failed toolsets added
            assert result is None
            assert len(service._connected_servers) == 0
            # Existing tools should still be present
            assert existing_tool in mock_agent.tools


class TestCleanup:
    """Tests for cleanup method."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_closes_connected_servers(self):
        """Test that cleanup closes all connected servers."""
        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Add mock connected servers
            mock_toolset1 = AsyncMock()
            mock_toolset1.close = AsyncMock()
            mock_toolset2 = AsyncMock()
            mock_toolset2.close = AsyncMock()

            service._connected_servers = [mock_toolset1, mock_toolset2]

            # Act
            await service.cleanup()

            # Assert
            mock_toolset1.close.assert_called_once()
            mock_toolset2.close.assert_called_once()
            assert service._connected_servers == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_handles_close_errors(self):
        """Test that cleanup handles errors during close gracefully."""
        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Add mock connected server that raises on close
            mock_toolset = AsyncMock()
            mock_toolset.close = AsyncMock(side_effect=Exception("Close failed"))

            service._connected_servers = [mock_toolset]

            # Act - should not raise
            await service.cleanup()

            # Assert - list should still be cleared
            assert service._connected_servers == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_handles_servers_without_close(self):
        """Test that cleanup handles servers without close method."""
        with patch(
            "microsoft_agents_a365.tooling.extensions.googleadk.services.mcp_tool_registration_service.McpToolServerConfigurationService"
        ):
            from microsoft_agents_a365.tooling.extensions.googleadk import McpToolRegistrationService

            service = McpToolRegistrationService()

            # Add mock connected server without close method
            mock_toolset = MagicMock(spec=[])  # Empty spec = no methods

            service._connected_servers = [mock_toolset]

            # Act - should not raise
            await service.cleanup()

            # Assert - list should still be cleared
            assert service._connected_servers == []

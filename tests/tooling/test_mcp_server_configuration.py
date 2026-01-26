# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for MCP Server Configuration Service."""

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents_a365.tooling.models import MCPServerConfig
from microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service import (
    McpToolServerConfigurationService,
)


class TestMCPServerConfig:
    """Tests for MCPServerConfig model."""

    def test_mcp_server_config_with_custom_url(self):
        """Test that MCPServerConfig can be created with a custom URL."""
        config = MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
            url="https://custom.mcp.server/endpoint",
        )

        assert config.mcp_server_name == "TestServer"
        assert config.mcp_server_unique_name == "test_server"
        assert config.url == "https://custom.mcp.server/endpoint"

    def test_mcp_server_config_without_custom_url(self):
        """Test that MCPServerConfig works without a custom URL."""
        config = MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
        )

        assert config.mcp_server_name == "TestServer"
        assert config.mcp_server_unique_name == "test_server"
        assert config.url is None

    def test_mcp_server_config_validation(self):
        """Test that MCPServerConfig validates required fields."""
        with pytest.raises(ValueError, match="mcp_server_name cannot be empty"):
            MCPServerConfig(mcp_server_name="", mcp_server_unique_name="test")

        with pytest.raises(ValueError, match="mcp_server_unique_name cannot be empty"):
            MCPServerConfig(mcp_server_name="test", mcp_server_unique_name="")


class TestMcpToolServerConfigurationService:
    """Tests for McpToolServerConfigurationService."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return McpToolServerConfigurationService()

    @pytest.fixture
    def mock_manifest_data(self) -> dict[str, Any]:
        """Create mock manifest data."""
        return {
            "mcpServers": [
                {
                    "mcpServerName": "TestServer1",
                    "mcpServerUniqueName": "test_server_1",
                },
                {
                    "mcpServerName": "TestServer2",
                    "mcpServerUniqueName": "test_server_2",
                    "url": "https://custom.server.com/mcp",
                },
            ]
        }

    def test_extract_server_url_from_manifest(self, service):
        """Test extracting custom URL from manifest element."""
        # Test with url field
        element = {"url": "https://custom.url.com"}
        url = service._extract_server_url(element)
        assert url == "https://custom.url.com"

        # Test with no URL
        element = {}
        url = service._extract_server_url(element)
        assert url is None

    def test_parse_manifest_server_config_with_custom_url(self, service):
        """Test parsing manifest config with custom URL."""
        server_element = {
            "mcpServerName": "CustomServer",
            "mcpServerUniqueName": "custom_server",
            "url": "https://my.custom.server/mcp",
        }

        config = service._parse_manifest_server_config(server_element)

        assert config is not None
        assert config.mcp_server_name == "CustomServer"
        assert config.mcp_server_unique_name == "custom_server"
        assert config.url == "https://my.custom.server/mcp"

    @patch(
        "microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service.build_mcp_server_url"
    )
    def test_parse_manifest_server_config_without_custom_url(self, mock_build_url, service):
        """Test parsing manifest config without custom URL constructs URL."""
        mock_build_url.return_value = "https://default.server/agents/servers/DefaultServer"

        server_element = {
            "mcpServerName": "DefaultServer",
            "mcpServerUniqueName": "test_server",
        }

        config = service._parse_manifest_server_config(server_element)

        assert config is not None
        assert config.mcp_server_name == "DefaultServer"
        assert config.mcp_server_unique_name == "test_server"
        # Without a custom URL, build_mcp_server_url constructs the full URL and stores it in the url field
        # Uses mcp_server_name if available, otherwise falls back to mcp_server_unique_name
        assert config.url == "https://default.server/agents/servers/DefaultServer"
        mock_build_url.assert_called_once_with("DefaultServer")

    def test_parse_gateway_server_config_with_custom_url(self, service):
        """Test parsing gateway config with custom URL."""
        server_element = {
            "mcpServerName": "GatewayServer",
            "mcpServerUniqueName": "gateway_server_endpoint",
            "url": "https://gateway.custom.url/mcp",
        }

        config = service._parse_gateway_server_config(server_element)

        assert config is not None
        assert config.mcp_server_name == "GatewayServer"
        assert config.mcp_server_unique_name == "gateway_server_endpoint"
        assert config.url == "https://gateway.custom.url/mcp"

    @patch(
        "microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service.build_mcp_server_url"
    )
    def test_parse_gateway_server_config_without_custom_url(self, mock_build_url, service):
        """Test parsing gateway config without custom URL."""
        mock_build_url.return_value = "https://default.server/agents/servers/GatewayServer"

        server_element = {
            "mcpServerName": "GatewayServer",
            "mcpServerUniqueName": "gateway_server",
        }

        config = service._parse_gateway_server_config(server_element)

        assert config is not None
        assert config.mcp_server_name == "GatewayServer"
        assert config.mcp_server_unique_name == "gateway_server"
        # Without a custom URL, build_mcp_server_url constructs the full URL and stores it in the url field
        # Uses mcp_server_name if available, otherwise falls back to mcp_server_unique_name
        assert config.url == "https://default.server/agents/servers/GatewayServer"
        mock_build_url.assert_called_once_with("GatewayServer")

    @patch.dict(os.environ, {"ENVIRONMENT": "Development"})
    def test_is_development_scenario(self, service):
        """Test development scenario detection."""
        assert service._is_development_scenario() is True

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    def test_is_production_scenario(self, service):
        """Test production scenario detection."""
        assert service._is_development_scenario() is False

    @patch.object(McpToolServerConfigurationService, "_load_servers_from_manifest")
    @patch.dict(os.environ, {"ENVIRONMENT": "Development"})
    @pytest.mark.asyncio
    async def test_list_tool_servers_development(self, mock_load_manifest, service):
        """Test listing servers in development mode."""
        mock_servers = [
            MCPServerConfig(
                mcp_server_name="DevServer",
                mcp_server_unique_name="dev_server",
                url="https://dev.server/mcp",
            )
        ]
        mock_load_manifest.return_value = mock_servers

        servers = await service.list_tool_servers(
            agentic_app_id="test-app-id", auth_token="test-token"
        )

        assert servers == mock_servers
        mock_load_manifest.assert_called_once()

    @patch(
        "microsoft_agents_a365.tooling.services.mcp_tool_server_configuration_service.get_tooling_gateway_for_digital_worker"
    )
    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_list_tool_servers_production_with_custom_url(self, mock_gateway_url, service):
        """Test listing servers in production mode with custom URL."""
        mock_gateway_url.return_value = "https://gateway.test/agents/test-app-id/mcpServers"

        # Mock aiohttp response
        mock_response_data = {
            "mcpServers": [
                {
                    "mcpServerName": "ProdServer",
                    "mcpServerUniqueName": "prod_server",
                    "url": "https://prod.custom.url/mcp",
                }
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create proper async context managers
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps(mock_response_data))

            # Create async context manager for response
            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)

            # Create async context manager for session
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response_cm)

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session_cm

            servers = await service.list_tool_servers(
                agentic_app_id="test-app-id", auth_token="test-token"
            )

            assert len(servers) == 1
            assert servers[0].mcp_server_name == "ProdServer"
            assert servers[0].mcp_server_unique_name == "prod_server"
            assert servers[0].url == "https://prod.custom.url/mcp"

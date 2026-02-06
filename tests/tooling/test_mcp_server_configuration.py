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


class TestPrepareGatewayHeaders:
    """Tests for _prepare_gateway_headers and _resolve_agent_id_for_header."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return McpToolServerConfigurationService()

    @pytest.fixture
    def create_test_jwt(self):
        """Fixture to create test JWT tokens."""
        import jwt

        def _create(claims: dict) -> str:
            return jwt.encode(claims, key="", algorithm="none")

        return _create

    @pytest.fixture
    def default_options(self):
        """Default ToolOptions for tests."""
        from microsoft_agents_a365.tooling.models import ToolOptions

        return ToolOptions(orchestrator_name="TestOrchestrator")

    def test_includes_authorization_header(self, service, default_options):
        """Test that Authorization header is always included."""
        headers = service._prepare_gateway_headers("test-token", default_options)
        assert headers["Authorization"] == "Bearer test-token"

    def test_includes_user_agent_header(self, service, default_options):
        """Test that User-Agent header is always included."""
        headers = service._prepare_gateway_headers("test-token", default_options)
        assert "User-Agent" in headers
        assert "Agent365SDK" in headers["User-Agent"]
        assert "TestOrchestrator" in headers["User-Agent"]

    def test_includes_x_ms_agentid_from_token_claims(
        self, service, create_test_jwt, default_options
    ):
        """Test x-ms-agentid header is populated from token claims."""
        token = create_test_jwt({"appid": "token-app-id-123"})
        headers = service._prepare_gateway_headers(token, default_options)
        assert headers.get("x-ms-agentid") == "token-app-id-123"

    def test_includes_x_ms_agentid_from_xms_par_app_azp(
        self, service, create_test_jwt, default_options
    ):
        """Test x-ms-agentid prefers xms_par_app_azp over appid."""
        token = create_test_jwt({
            "xms_par_app_azp": "blueprint-id-from-token",
            "appid": "app-id-456",
        })
        headers = service._prepare_gateway_headers(token, default_options)
        assert headers.get("x-ms-agentid") == "blueprint-id-from-token"

    def test_includes_x_ms_agentid_from_turn_context_blueprint_id(
        self, service, create_test_jwt, default_options
    ):
        """Test x-ms-agentid prefers TurnContext agenticAppBlueprintId over token."""
        token = create_test_jwt({"appid": "token-app-id"})

        # Create mock TurnContext with agenticAppBlueprintId
        mock_from = MagicMock()
        mock_from.agentic_app_blueprint_id = "context-blueprint-id"
        mock_activity = MagicMock()
        mock_activity.from_ = mock_from
        mock_context = MagicMock()
        mock_context.activity = mock_activity

        headers = service._prepare_gateway_headers(token, default_options, mock_context)
        assert headers.get("x-ms-agentid") == "context-blueprint-id"

    def test_falls_back_to_application_name(self, service, create_test_jwt, default_options):
        """Test x-ms-agentid falls back to application name when no token claims."""
        # Token with no relevant claims
        token = create_test_jwt({"sub": "some-subject"})

        with patch(
            "microsoft_agents_a365.runtime.utility.Utility.get_application_name",
            return_value="my-application",
        ):
            headers = service._prepare_gateway_headers(token, default_options)
            assert headers.get("x-ms-agentid") == "my-application"

    def test_omits_x_ms_agentid_when_nothing_available(
        self, service, create_test_jwt, default_options
    ):
        """Test x-ms-agentid header is omitted when no identifier is available."""
        # Token with no relevant claims
        token = create_test_jwt({"sub": "some-subject"})

        with patch(
            "microsoft_agents_a365.runtime.utility.Utility.get_application_name",
            return_value=None,
        ):
            headers = service._prepare_gateway_headers(token, default_options)
            assert "x-ms-agentid" not in headers


class TestResolveAgentIdForHeader:
    """Tests for _resolve_agent_id_for_header method."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return McpToolServerConfigurationService()

    @pytest.fixture
    def create_test_jwt(self):
        """Fixture to create test JWT tokens."""
        import jwt as pyjwt

        def _create(claims: dict) -> str:
            return pyjwt.encode(claims, key="", algorithm="none")

        return _create

    def test_priority_1_turn_context_blueprint_id(self, service, create_test_jwt):
        """Test TurnContext agenticAppBlueprintId has highest priority."""
        token = create_test_jwt({
            "xms_par_app_azp": "token-blueprint",
            "appid": "token-appid",
        })

        mock_from = MagicMock()
        mock_from.agentic_app_blueprint_id = "context-blueprint-id"
        mock_activity = MagicMock()
        mock_activity.from_ = mock_from
        mock_context = MagicMock()
        mock_context.activity = mock_activity

        result = service._resolve_agent_id_for_header(token, mock_context)
        assert result == "context-blueprint-id"

    def test_priority_2_token_xms_par_app_azp(self, service, create_test_jwt):
        """Test token xms_par_app_azp claim is second priority."""
        token = create_test_jwt({
            "xms_par_app_azp": "token-blueprint",
            "appid": "token-appid",
        })

        result = service._resolve_agent_id_for_header(token, None)
        assert result == "token-blueprint"

    def test_priority_3_token_appid(self, service, create_test_jwt):
        """Test token appid claim is third priority."""
        token = create_test_jwt({"appid": "token-appid"})

        result = service._resolve_agent_id_for_header(token, None)
        assert result == "token-appid"

    def test_priority_4_application_name(self, service, create_test_jwt):
        """Test application name is lowest priority."""
        token = create_test_jwt({"sub": "no-relevant-claims"})

        with patch(
            "microsoft_agents_a365.runtime.utility.Utility.get_application_name",
            return_value="fallback-app-name",
        ):
            result = service._resolve_agent_id_for_header(token, None)
            assert result == "fallback-app-name"

    def test_returns_none_when_nothing_available(self, service, create_test_jwt):
        """Test returns None when no identifier is available."""
        token = create_test_jwt({"sub": "no-relevant-claims"})

        with patch(
            "microsoft_agents_a365.runtime.utility.Utility.get_application_name",
            return_value=None,
        ):
            result = service._resolve_agent_id_for_header(token, None)
            assert result is None

    def test_handles_turn_context_without_activity(self, service, create_test_jwt):
        """Test handles TurnContext with None activity gracefully."""
        token = create_test_jwt({"appid": "token-appid"})

        mock_context = MagicMock()
        mock_context.activity = None

        result = service._resolve_agent_id_for_header(token, mock_context)
        assert result == "token-appid"

    def test_handles_turn_context_without_from(self, service, create_test_jwt):
        """Test handles TurnContext activity with None from_ gracefully."""
        token = create_test_jwt({"appid": "token-appid"})

        mock_activity = MagicMock()
        mock_activity.from_ = None
        mock_context = MagicMock()
        mock_context.activity = mock_activity

        result = service._resolve_agent_id_for_header(token, mock_context)
        assert result == "token-appid"

    def test_handles_turn_context_without_blueprint_id_attribute(self, service, create_test_jwt):
        """Test handles from_ object without agentic_app_blueprint_id attribute."""
        token = create_test_jwt({"appid": "token-appid"})

        # Mock from_ that doesn't have agentic_app_blueprint_id
        mock_from = MagicMock(spec=[])  # Empty spec means no attributes
        mock_activity = MagicMock()
        mock_activity.from_ = mock_from
        mock_context = MagicMock()
        mock_context.activity = mock_activity

        result = service._resolve_agent_id_for_header(token, mock_context)
        assert result == "token-appid"

    def test_skips_empty_blueprint_id(self, service, create_test_jwt):
        """Test skips empty string blueprint ID from TurnContext."""
        token = create_test_jwt({"appid": "token-appid"})

        mock_from = MagicMock()
        mock_from.agentic_app_blueprint_id = ""  # Empty string
        mock_activity = MagicMock()
        mock_activity.from_ = mock_from
        mock_context = MagicMock()
        mock_context.activity = mock_activity

        result = service._resolve_agent_id_for_header(token, mock_context)
        assert result == "token-appid"

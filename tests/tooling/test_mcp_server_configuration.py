# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for MCP Server Configuration Service."""

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

        config = service._parse_server_config(server_element)

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

        config = service._parse_server_config(server_element)

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

        config = service._parse_server_config(server_element)

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

        config = service._parse_server_config(server_element)

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
        # V1 server (no audience) — this test verifies URL preservation, not token exchange.
        # V2 servers (with a non-ATG audience) require auth context to be passed; that
        # behaviour is tested separately in the per-audience token tests.
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
            mock_response.json = AsyncMock(return_value=mock_response_data)

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

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_legacy_prod_path_raises_for_v2_server(self, service):
        """Legacy call (no auth context) raises immediately when a V2 server is discovered.

        Callers that omit
        authorization/auth_handler_name/turn_context must migrate to the full
        TurnContext overload once V2 servers are present.
        """
        v2_server_data = {
            "mcpServers": [
                {
                    "mcpServerName": "V2Server",
                    "mcpServerUniqueName": "v2_server",
                    "url": "https://v2.example.com/mcp",
                    "audience": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                }
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=v2_server_data)
            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response_cm)
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            with pytest.raises(Exception, match="V2Server"):
                await service.list_tool_servers(
                    agentic_app_id="test-app-id",
                    auth_token="test-token",
                    # No authorization / auth_handler_name / turn_context → legacy path
                )

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_legacy_prod_path_ok_for_v1_only_servers(self, service):
        """Legacy call succeeds when all discovered servers are V1 (no audience)."""
        v1_server_data = {
            "mcpServers": [
                {
                    "mcpServerName": "V1Server",
                    "mcpServerUniqueName": "v1_server",
                    "url": "https://v1.example.com/mcp",
                }
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=v1_server_data)
            mock_response_cm = MagicMock()
            mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response_cm)
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            servers = await service.list_tool_servers(
                agentic_app_id="test-app-id",
                auth_token="test-token",
                # No authorization context — fine for V1-only
            )

        assert len(servers) == 1
        assert servers[0].mcp_server_name == "V1Server"


class TestResolveTokenScopeForServer:
    """Tests for resolve_token_scope_for_server() utility function."""

    PROD_ATG_APP_ID = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1"
    TEST_ATG_APP_ID = "05879165-0320-489e-b644-f72b33f3edf0"
    V2_GUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def _make_server(
        self, audience: str | None = None, scope: str | None = None
    ) -> MCPServerConfig:
        return MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
            audience=audience,
            scope=scope,
        )

    # ------------------------------------------------------------------
    # V1 scenarios — all fall back to shared ATG scope
    # ------------------------------------------------------------------

    def test_v1_no_audience_returns_atg_scope(self):
        """V1: no audience → shared ATG /.default."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience=None, scope=None)
        assert resolve_token_scope_for_server(server) == f"{self.PROD_ATG_APP_ID}/.default"

    def test_v1_atg_guid_audience_falls_back_to_atg_scope(self):
        """V1: audience == ATG AppId bare GUID → shared ATG /.default."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience=self.PROD_ATG_APP_ID, scope="McpServers.Teams.All")
        assert resolve_token_scope_for_server(server) == f"{self.PROD_ATG_APP_ID}/.default"

    def test_v1_atg_audience_in_uri_form_falls_back_to_atg_scope(self):
        """V1: audience == api://<atg-guid> → shared ATG /.default."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience=f"api://{self.PROD_ATG_APP_ID}")
        assert resolve_token_scope_for_server(server) == f"{self.PROD_ATG_APP_ID}/.default"

    # ------------------------------------------------------------------
    # V1 test-env — non-prod ATG audience falls through to V2 scope resolution
    # ------------------------------------------------------------------

    def test_v1_test_env_shared_audience_not_treated_as_v2(self):
        """Non-prod ATG audience GUID is different from the hardcoded prod ATG_APP_ID constant,
        so it is classified as V2 and resolved to its own /.default scope. This is intentional:
        the V2 token exchange works correctly for test app registrations because
        Tools.ListInvoke.All is pre-consented. Use MCP_PLATFORM_AUTHENTICATION_SCOPE or
        MCP_PLATFORM_ENDPOINT env vars to point the SDK at a non-prod gateway."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        # Non-prod ATG audience — classified as V2 because it does not match
        # the hardcoded prod ATG_APP_ID constant. Resolved to its own /.default scope.
        server = self._make_server(audience=self.TEST_ATG_APP_ID, scope=None)
        assert resolve_token_scope_for_server(server) == f"{self.TEST_ATG_APP_ID}/.default"

    # ------------------------------------------------------------------
    # V2 scenarios — unique audience, explicit scope
    # ------------------------------------------------------------------

    def test_v2_guid_audience_with_explicit_scope(self):
        """V2: unique GUID audience + explicit scope → <guid>/<scope>."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience=self.V2_GUID, scope="Tools.ListInvoke.All")
        assert resolve_token_scope_for_server(server) == f"{self.V2_GUID}/Tools.ListInvoke.All"

    def test_v2_api_uri_audience_with_explicit_scope(self):
        """V2: api:// audience + explicit scope → api://<guid>/<scope>."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(
            audience="api://mcp-calendartools", scope="McpServers.Calendar.All"
        )
        assert (
            resolve_token_scope_for_server(server)
            == "api://mcp-calendartools/McpServers.Calendar.All"
        )

    def test_v2_guid_audience_null_scope_falls_back_to_default(self):
        """V2: unique GUID audience + null scope → <guid>/.default (pre-consented)."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience=self.V2_GUID, scope=None)
        assert resolve_token_scope_for_server(server) == f"{self.V2_GUID}/.default"

    def test_v2_api_uri_audience_null_scope_falls_back_to_default(self):
        """V2: api:// audience + null scope → api://<guid>/.default (pre-consented)."""
        from microsoft_agents_a365.tooling.utils.utility import resolve_token_scope_for_server

        server = self._make_server(audience="api://mcp-mailtools", scope=None)
        assert resolve_token_scope_for_server(server) == "api://mcp-mailtools/.default"


class TestAttachPerAudienceTokens:
    """Tests for McpToolServerConfigurationService._attach_per_audience_tokens().

    Since _attach_per_audience_tokens now accepts a TokenAcquirer callable,
    these tests use service._create_obo_token_acquirer() to build the acquirer
    from a mock authorization object — matching real production usage.
    """

    ATG_APP_ID = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1"

    @pytest.fixture
    def service(self):
        return McpToolServerConfigurationService()

    def _make_server(self, name: str, audience: str | None = None) -> MCPServerConfig:
        return MCPServerConfig(
            mcp_server_name=name,
            mcp_server_unique_name=name.lower(),
            url=f"https://{name}.example.com/mcp",
            audience=audience,
        )

    def _make_auth_context(self, token: str = "tok"):
        authorization = MagicMock()
        token_result = MagicMock()
        token_result.token = token
        authorization.exchange_token = AsyncMock(return_value=token_result)
        turn_context = MagicMock()
        return authorization, turn_context

    @pytest.mark.asyncio
    async def test_v1_server_gets_atg_token(self, service):
        """V1 server (no audience) receives ATG-scoped token."""
        servers = [self._make_server("mail")]
        authorization, turn_context = self._make_auth_context("atg-token")
        acquire = service._create_obo_token_acquirer(authorization, "handler", turn_context)

        result = await service._attach_per_audience_tokens(servers, acquire)

        assert len(result) == 1
        assert result[0].headers["Authorization"] == "Bearer atg-token"
        authorization.exchange_token.assert_called_once_with(
            turn_context, [f"{self.ATG_APP_ID}/.default"], "handler"
        )

    @pytest.mark.asyncio
    async def test_v2_server_gets_per_audience_token(self, service):
        """V2 server gets token scoped to its own audience GUID."""
        guid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        servers = [self._make_server("calendar", audience=guid)]
        authorization, turn_context = self._make_auth_context("v2-token")
        acquire = service._create_obo_token_acquirer(authorization, "handler", turn_context)

        result = await service._attach_per_audience_tokens(servers, acquire)

        assert result[0].headers["Authorization"] == "Bearer v2-token"
        authorization.exchange_token.assert_called_once_with(
            turn_context, [f"{guid}/.default"], "handler"
        )

    @pytest.mark.asyncio
    async def test_multiple_v1_servers_share_one_token_exchange(self, service):
        """Multiple V1 servers deduplicate to a single token exchange."""
        servers = [
            self._make_server("mail"),
            self._make_server("calendar"),
            self._make_server("files"),
        ]
        authorization, turn_context = self._make_auth_context("shared-atg-token")
        acquire = service._create_obo_token_acquirer(authorization, "handler", turn_context)

        result = await service._attach_per_audience_tokens(servers, acquire)

        assert all(s.headers["Authorization"] == "Bearer shared-atg-token" for s in result)
        authorization.exchange_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_v1_v2_servers_deduplicate_by_scope(self, service):
        """Mixed V1/V2 list: one exchange per unique scope."""
        guid1 = "aaaaaaaa-0000-0000-0000-000000000001"
        guid2 = "bbbbbbbb-0000-0000-0000-000000000002"
        servers = [
            self._make_server("mail"),  # V1
            self._make_server("cal1", guid1),  # V2 guid1
            self._make_server("cal2", guid2),  # V2 guid2
            self._make_server("files"),  # V1 (same scope as mail → no 2nd exchange)
            self._make_server("cal3", guid1),  # V2 guid1 again → no 2nd exchange
        ]

        authorization = MagicMock()
        call_count = [0]

        async def fake_exchange(ctx, scopes, handler):
            call_count[0] += 1
            result = MagicMock()
            result.token = f"token-for-{scopes[0]}"
            return result

        authorization.exchange_token = fake_exchange
        turn_context = MagicMock()
        acquire = service._create_obo_token_acquirer(authorization, "handler", turn_context)

        result = await service._attach_per_audience_tokens(servers, acquire)

        assert call_count[0] == 3  # ATG + guid1 + guid2
        assert result[0].headers["Authorization"] == f"Bearer token-for-{self.ATG_APP_ID}/.default"
        assert result[1].headers["Authorization"] == f"Bearer token-for-{guid1}/.default"
        assert result[2].headers["Authorization"] == f"Bearer token-for-{guid2}/.default"
        assert result[3].headers["Authorization"] == f"Bearer token-for-{self.ATG_APP_ID}/.default"
        assert result[4].headers["Authorization"] == f"Bearer token-for-{guid1}/.default"

    @pytest.mark.asyncio
    async def test_raises_when_token_exchange_returns_none(self, service):
        """Exception raised when OBO token exchange returns None."""
        servers = [self._make_server("mail")]
        authorization = MagicMock()
        authorization.exchange_token = AsyncMock(return_value=None)
        acquire = service._create_obo_token_acquirer(authorization, "handler", MagicMock())

        with pytest.raises(Exception, match="Failed to obtain token"):
            await service._attach_per_audience_tokens(servers, acquire)

    @pytest.mark.asyncio
    async def test_raises_when_token_is_empty(self, service):
        """Exception raised when OBO token result has an empty token string."""
        servers = [self._make_server("mail")]
        authorization = MagicMock()
        token_result = MagicMock()
        token_result.token = ""
        authorization.exchange_token = AsyncMock(return_value=token_result)
        acquire = service._create_obo_token_acquirer(authorization, "handler", MagicMock())

        with pytest.raises(Exception, match="Failed to obtain token"):
            await service._attach_per_audience_tokens(servers, acquire)

    @pytest.mark.asyncio
    async def test_preserves_existing_server_headers(self, service):
        """Existing server headers are preserved alongside the new Authorization header."""
        server = MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
            url="https://test.example.com/mcp",
            headers={"X-Custom": "my-value"},
        )
        authorization, turn_context = self._make_auth_context("tok")
        acquire = service._create_obo_token_acquirer(authorization, "handler", turn_context)

        result = await service._attach_per_audience_tokens([server], acquire)

        assert result[0].headers["X-Custom"] == "my-value"
        assert result[0].headers["Authorization"] == "Bearer tok"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "env_value",
        [
            "Bearer rawtoken123",
            "bearer rawtoken123",
            "BEARER rawtoken123",
            "BeArEr rawtoken123",
        ],
    )
    async def test_dev_acquirer_strips_bearer_prefix(self, service, env_value):
        """Dev acquirer strips an existing 'Bearer ' prefix to prevent doubled headers."""
        server = self._make_server("mail")
        with patch.dict(os.environ, {"BEARER_TOKEN": env_value}):
            acquire = service._create_dev_token_acquirer()
            result = await service._attach_per_audience_tokens([server], acquire)

        assert result[0].headers["Authorization"] == "Bearer rawtoken123"

    @pytest.mark.asyncio
    async def test_dev_acquirer_raw_token_unchanged(self, service):
        """Dev acquirer leaves a raw token (no prefix) unchanged."""
        server = self._make_server("mail")
        with patch.dict(os.environ, {"BEARER_TOKEN": "rawtoken456"}):
            acquire = service._create_dev_token_acquirer()
            result = await service._attach_per_audience_tokens([server], acquire)

        assert result[0].headers["Authorization"] == "Bearer rawtoken456"

    @pytest.mark.asyncio
    async def test_dev_acquirer_per_server_token_strips_bearer_prefix(self, service):
        """Per-server BEARER_TOKEN_<NAME> env var also has its Bearer prefix stripped."""
        server = self._make_server("mail")
        with patch.dict(os.environ, {"BEARER_TOKEN_MAIL": "Bearer per-server-tok"}):
            acquire = service._create_dev_token_acquirer()
            result = await service._attach_per_audience_tokens([server], acquire)

        assert result[0].headers["Authorization"] == "Bearer per-server-tok"

    @pytest.mark.asyncio
    async def test_dev_acquirer_warns_when_shared_token_used_for_v2_server(self, service):
        """Warning emitted when BEARER_TOKEN is used for a V2 server with a different scope."""
        v2_server = self._make_server("MailV2", audience="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        with patch.dict(
            os.environ,
            {"BEARER_TOKEN": "shared-token"},
            clear=False,
        ):
            # Ensure the per-server key is absent so the fallback path is taken.
            os.environ.pop("BEARER_TOKEN_MAILV2", None)
            with patch.object(service, "_logger") as mock_logger:
                acquire = service._create_dev_token_acquirer()
                await service._attach_per_audience_tokens([v2_server], acquire)
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "BEARER_TOKEN_MAILV2" in warning_msg
                assert "401" in warning_msg

    @pytest.mark.asyncio
    async def test_dev_acquirer_no_warning_when_per_server_token_set(self, service):
        """No warning when a per-server BEARER_TOKEN_<NAME> is present for a V2 server."""
        v2_server = self._make_server("MailV2", audience="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        with patch.dict(
            os.environ,
            {"BEARER_TOKEN": "shared-token", "BEARER_TOKEN_MAILV2": "per-server-token"},
        ):
            with patch.object(service, "_logger") as mock_logger:
                acquire = service._create_dev_token_acquirer()
                await service._attach_per_audience_tokens([v2_server], acquire)
                mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_dev_acquirer_no_warning_for_v1_server(self, service):
        """No warning when shared BEARER_TOKEN is used for a V1 server (scope == shared scope)."""
        v1_server = self._make_server("mail")  # no audience → V1 → scope == shared_scope
        with patch.dict(os.environ, {"BEARER_TOKEN": "shared-token"}):
            os.environ.pop("BEARER_TOKEN_MAIL", None)
            with patch.object(service, "_logger") as mock_logger:
                acquire = service._create_dev_token_acquirer()
                await service._attach_per_audience_tokens([v1_server], acquire)
                mock_logger.warning.assert_not_called()


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

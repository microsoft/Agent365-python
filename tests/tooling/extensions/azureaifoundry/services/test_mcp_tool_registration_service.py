# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for add_tool_servers_to_agent in the AzureAIFoundry McpToolRegistrationService.

These tests verify that:
- list_tool_servers() is called with the full authorization context so that
  _attach_per_audience_tokens() runs and V2 per-audience tokens are used.
- Each McpTool receives the per-server Authorization header from server.headers,
  not the shared discovery auth_token.
- The User-Agent header is set on every McpTool.
- The fallback to the shared auth_token works when server.headers has no
  Authorization (defensive path).
"""

from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest
from microsoft_agents_a365.tooling.extensions.azureaifoundry.services import (
    McpToolRegistrationService,
)
from microsoft_agents_a365.tooling.utils.constants import Constants

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MODULE = (
    "microsoft_agents_a365.tooling.extensions.azureaifoundry.services.mcp_tool_registration_service"
)


def _make_mock_server(auth_header: str | None = None):
    """Create a minimal MCPServerConfig mock with optional Authorization header."""
    server = Mock()
    server.mcp_server_name = "mcp_TestServer"
    server.mcp_server_unique_name = "test_server"
    server.url = "https://test-mcp.example.com/mcp"
    server.headers = (
        {Constants.Headers.AUTHORIZATION: auth_header} if auth_header is not None else {}
    )
    return server


def _make_mock_mcp_tool():
    """Create a minimal McpTool mock that records update_headers calls."""
    tool = MagicMock()
    tool.definitions = [Mock()]
    tool.resources = None
    return tool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_turn_context():
    context = Mock()
    context.activity = Mock()
    context.activity.conversation = Mock()
    context.activity.conversation.id = "conv-123"
    context.activity.id = "msg-456"
    context.activity.text = "hello"
    return context


@pytest.fixture
def mock_auth():
    auth = AsyncMock()
    token_result = Mock()
    token_result.token = "discovery-token"
    auth.exchange_token = AsyncMock(return_value=token_result)
    return auth


@pytest.fixture
def mock_project_client():
    client = Mock()
    client.agents = Mock()
    client.agents.update_agent = Mock()
    return client


@pytest.fixture
def service():
    svc = McpToolRegistrationService()
    svc._mcp_server_configuration_service = Mock()
    return svc


# ---------------------------------------------------------------------------
# Tests — auth context forwarded to list_tool_servers
# ---------------------------------------------------------------------------


class TestAuthContextForwardedToListToolServers:
    """Verify list_tool_servers is called with authorization/auth_handler_name/turn_context."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_list_tool_servers_receives_auth_context(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """list_tool_servers must receive the full auth context so per-audience
        token exchange runs for V2 MCP servers."""
        auth_token = "discovery-token"
        mock_server = _make_mock_server("Bearer per-audience-token")
        mock_mcp_tool = _make_mock_mcp_tool()

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[mock_server]
        )

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.is_development_environment", return_value=False),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="AzureAIFoundry/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="test-handler",
                context=mock_turn_context,
                auth_token=auth_token,
            )

        service._mcp_server_configuration_service.list_tool_servers.assert_awaited_once_with(
            "test-aai",
            auth_token,
            ANY,  # ToolOptions — any value
            authorization=mock_auth,
            auth_handler_name="test-handler",
            turn_context=mock_turn_context,
        )

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_list_tool_servers_called_with_correct_keyword_args(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """Verify keyword argument names match list_tool_servers signature exactly."""
        auth_token = "token-xyz"
        mock_server = _make_mock_server("Bearer v2-token")
        mock_mcp_tool = _make_mock_mcp_tool()

        list_tool_servers_mock = AsyncMock(return_value=[mock_server])
        service._mcp_server_configuration_service.list_tool_servers = list_tool_servers_mock

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="aai-123"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="UA/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler-name",
                context=mock_turn_context,
                auth_token=auth_token,
            )

        _, kwargs = list_tool_servers_mock.call_args
        assert kwargs["authorization"] is mock_auth
        assert kwargs["auth_handler_name"] == "handler-name"
        assert kwargs["turn_context"] is mock_turn_context


# ---------------------------------------------------------------------------
# Tests — per-server Authorization header on McpTool
# ---------------------------------------------------------------------------


class TestPerServerAuthorizationHeader:
    """Verify McpTool receives the per-audience token from server.headers, not
    the shared discovery auth_token."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mcp_tool_uses_per_server_auth_header_not_shared_token(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """McpTool.update_headers must be called with the per-audience token
        attached by _attach_per_audience_tokens(), not the shared discovery token."""
        discovery_token = "shared-atg-discovery-token"
        per_audience_token = "Bearer per-audience-v2-token"

        mock_server = _make_mock_server(auth_header=per_audience_token)
        mock_mcp_tool = _make_mock_mcp_tool()

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[mock_server]
        )

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="UA/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler",
                context=mock_turn_context,
                auth_token=discovery_token,
            )

        auth_calls = [
            call
            for call in mock_mcp_tool.update_headers.call_args_list
            if call.args[0] == Constants.Headers.AUTHORIZATION
        ]
        assert len(auth_calls) == 1
        assert auth_calls[0].args[1] == per_audience_token
        # Must NOT use the shared discovery token
        assert auth_calls[0].args[1] != f"Bearer {discovery_token}"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mcp_tool_falls_back_to_shared_token_when_server_headers_empty(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """When server.headers has no Authorization (dev manifest path or empty),
        fall back to wrapping auth_token as Bearer."""
        auth_token = "fallback-token"
        mock_server = _make_mock_server(auth_header=None)  # no header
        mock_mcp_tool = _make_mock_mcp_tool()

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[mock_server]
        )

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="UA/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler",
                context=mock_turn_context,
                auth_token=auth_token,
            )

        auth_calls = [
            call
            for call in mock_mcp_tool.update_headers.call_args_list
            if call.args[0] == Constants.Headers.AUTHORIZATION
        ]
        assert len(auth_calls) == 1
        assert auth_calls[0].args[1] == f"Bearer {auth_token}"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mcp_tool_does_not_double_prefix_bearer_token(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """If auth_token already starts with 'Bearer ', it must not be double-prefixed."""
        auth_token = "Bearer already-prefixed-token"
        mock_server = _make_mock_server(auth_header=None)
        mock_mcp_tool = _make_mock_mcp_tool()

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[mock_server]
        )

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="UA/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler",
                context=mock_turn_context,
                auth_token=auth_token,
            )

        auth_calls = [
            call
            for call in mock_mcp_tool.update_headers.call_args_list
            if call.args[0] == Constants.Headers.AUTHORIZATION
        ]
        assert len(auth_calls) == 1
        assert auth_calls[0].args[1] == auth_token  # unchanged


# ---------------------------------------------------------------------------
# Tests — User-Agent header
# ---------------------------------------------------------------------------


class TestUserAgentHeader:
    """Verify the User-Agent header is set on every McpTool."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mcp_tool_has_user_agent_header(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """McpTool.update_headers must be called with User-Agent."""
        expected_ua = "AzureAIFoundry/1.0"
        mock_server = _make_mock_server(auth_header="Bearer token")
        mock_mcp_tool = _make_mock_mcp_tool()

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[mock_server]
        )

        with (
            patch(f"{_MODULE}.McpTool", return_value=mock_mcp_tool),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value=expected_ua),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler",
                context=mock_turn_context,
                auth_token="token",
            )

        ua_calls = [
            call
            for call in mock_mcp_tool.update_headers.call_args_list
            if call.args[0] == Constants.Headers.USER_AGENT
        ]
        assert len(ua_calls) == 1
        assert ua_calls[0].args[1] == expected_ua


# ---------------------------------------------------------------------------
# Tests — multiple servers: each gets its own token
# ---------------------------------------------------------------------------


class TestMultipleServers:
    """Verify each server in the list gets its own per-audience token."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_each_server_gets_its_own_per_audience_token(
        self, service, mock_turn_context, mock_auth, mock_project_client
    ):
        """Two servers with different per-audience tokens must each pass their
        own token — not the other server's token or the shared token."""
        token_v1 = "Bearer v1-atg-token"
        token_v2 = "Bearer v2-per-audience-token"

        server_v1 = _make_mock_server(auth_header=token_v1)
        server_v2 = _make_mock_server(auth_header=token_v2)
        server_v2.mcp_server_name = "mcp_AnotherServer"
        server_v2.mcp_server_unique_name = "another_server"

        tool_v1 = _make_mock_mcp_tool()
        tool_v2 = _make_mock_mcp_tool()
        tool_iter = iter([tool_v1, tool_v2])

        service._mcp_server_configuration_service.list_tool_servers = AsyncMock(
            return_value=[server_v1, server_v2]
        )

        with (
            patch(f"{_MODULE}.McpTool", side_effect=lambda **_: next(tool_iter)),
            patch(f"{_MODULE}.Utility.resolve_agent_identity", return_value="test-aai"),
            patch(f"{_MODULE}.Utility.get_user_agent_header", return_value="UA/1.0"),
        ):
            await service.add_tool_servers_to_agent(
                project_client=mock_project_client,
                auth=mock_auth,
                auth_handler_name="handler",
                context=mock_turn_context,
                auth_token="shared-discovery-token",
            )

        def _get_auth(tool):
            calls = [
                c
                for c in tool.update_headers.call_args_list
                if c.args[0] == Constants.Headers.AUTHORIZATION
            ]
            return calls[0].args[1] if calls else None

        assert _get_auth(tool_v1) == token_v1
        assert _get_auth(tool_v2) == token_v2

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests that add_tool_servers_to_agent never reuses another identity's MCP server token."""

import asyncio
import contextlib
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from agents import Agent, GuardrailFunctionOutput, InputGuardrail
from agents.mcp import MCPServerStreamableHttp
from microsoft_agents_a365.tooling.extensions.openai import McpToolRegistrationService
from microsoft_agents_a365.tooling.extensions.openai.mcp_tool_registration_service import (
    _DedicatedTaskMCPServer,
)
from microsoft_agents_a365.tooling.models import MCPServerConfig

MODULE = "microsoft_agents_a365.tooling.extensions.openai.mcp_tool_registration_service"


def server_url(name: str) -> str:
    return f"https://mcp.example.com/{name}"


class FakeStreamableHttpServer:
    """Stands in for the SDK's MCP server and records the headers it was created with."""

    def __init__(self, params: dict[str, object], name: str, harness: "Harness") -> None:
        self.params = params
        self.name = name
        self.closed = False
        self.session: object | None = None
        self._harness = harness

    async def connect(self) -> None:
        if self._harness.fail_connect:
            raise ConnectionError("connect failed")
        self.session = object()

    async def cleanup(self) -> None:
        self.closed = True
        self.session = None


class Harness:
    """Controls MCP discovery and connections for one test."""

    def __init__(self) -> None:
        self.discovered: list[str] = ["mail"]
        self.fail_connect = False
        self.fail_discovery = False
        self.created: list[FakeStreamableHttpServer] = []

    async def list_tool_servers(
        self, agentic_app_id: str, auth_token: str, options: object, **kwargs: object
    ) -> list[MCPServerConfig]:
        if self.fail_discovery:
            raise RuntimeError("discovery failed")
        # Mirrors list_tool_servers attaching the caller's per-audience token to each server.
        return [
            MCPServerConfig(
                mcp_server_name=name,
                mcp_server_unique_name=name,
                url=server_url(name),
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            for name in self.discovered
        ]

    def create_server(self, params: dict[str, object], name: str) -> FakeStreamableHttpServer:
        server = FakeStreamableHttpServer(params, name, self)
        self.created.append(server)
        return server


class FakeTransport:
    """Mimics the MCP client transport behind MCPServerStreamableHttp.

    connect() keeps an anyio task group open in the task that calls it, and a request that fails
    inside it (like a server rejecting the caller with HTTP 403) cancels that task.
    """

    def __init__(self) -> None:
        self.rejected_urls: set[str] = set()

    async def connect(self, server: MCPServerStreamableHttp) -> None:
        task_group = anyio.create_task_group()
        await task_group.__aenter__()
        server.test_task_group = task_group
        server.connected_in = asyncio.current_task()
        if server.params["url"] in self.rejected_urls:
            task_group.start_soon(self._reject)
            # Waits for the initialize response; the failed request cancels this task.
            await anyio.sleep(10)
        server.session = MagicMock()

    async def cleanup(self, server: MCPServerStreamableHttp) -> None:
        server.cleaned_up_in = asyncio.current_task()
        server.session = None
        task_group = getattr(server, "test_task_group", None)
        server.test_task_group = None
        if task_group is not None:
            task_group.cancel_scope.cancel()
            with contextlib.suppress(Exception):
                await task_group.__aexit__(None, None, None)

    @staticmethod
    async def _reject() -> None:
        raise PermissionError("HTTP 403 Forbidden")


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    fake = FakeTransport()

    async def connect(server: MCPServerStreamableHttp) -> None:
        await fake.connect(server)

    async def cleanup(server: MCPServerStreamableHttp) -> None:
        await fake.cleanup(server)

    monkeypatch.setattr(MCPServerStreamableHttp, "connect", connect)
    monkeypatch.setattr(MCPServerStreamableHttp, "cleanup", cleanup)
    return fake


@pytest.fixture
def discovery() -> Iterator[Harness]:
    """Patches MCP discovery; the service creates real MCP server objects."""
    test_harness = Harness()
    config_service = MagicMock()
    config_service.list_tool_servers = AsyncMock(side_effect=test_harness.list_tool_servers)
    with (
        patch(f"{MODULE}.McpToolServerConfigurationService", return_value=config_service),
        patch(f"{MODULE}.Utility") as utility,
        patch(f"{MODULE}.is_development_environment", return_value=False),
    ):
        utility.resolve_agent_identity.return_value = "agent-123"
        utility.get_user_agent_header.return_value = "Agent365SDK/test"
        yield test_harness


@pytest.fixture
def harness(discovery: Harness) -> Iterator[Harness]:
    """Patches MCP discovery and replaces the service's MCP servers with fakes."""
    with patch(f"{MODULE}._DedicatedTaskMCPServer", side_effect=discovery.create_server):
        yield discovery


async def run_turn(service: McpToolRegistrationService, agent: Agent, token: str) -> Agent:
    return await service.add_tool_servers_to_agent(
        agent=agent,
        auth=MagicMock(),
        auth_handler_name="agentic",
        context=MagicMock(),
        auth_token=token,
    )


def authorization_by_server(agent: Agent) -> dict[str, str]:
    return {server.name: server.params["headers"]["Authorization"] for server in agent.mcp_servers}


def new_agent() -> Agent:
    return Agent(name="test-agent", instructions="You are a test agent.")


class TestMcpServerIdentityIsolation:
    """A reused agent must only call MCP servers with the current turn's token."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_reused_agent_gets_current_identity_token(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        agent_b = await run_turn(service, agent_a, "user-b-token")

        assert authorization_by_server(agent_b) == {"mail": "Bearer user-b-token"}
        # The agent returned for user A is not modified.
        assert authorization_by_server(agent_a) == {"mail": "Bearer user-a-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cloned_agent_gets_current_identity_token(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        personalized = agent_a.clone(instructions="Personalized for user B.")
        agent_b = await run_turn(service, personalized, "user-b-token")

        assert authorization_by_server(agent_b) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_servers_from_another_service_instance_are_replaced(
        self, harness: Harness
    ) -> None:
        agent_a = await run_turn(McpToolRegistrationService(), new_agent(), "user-a-token")
        agent_b = await run_turn(McpToolRegistrationService(), agent_a, "user-b-token")

        assert authorization_by_server(agent_b) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_same_token_reuses_existing_connection(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        first = await run_turn(service, new_agent(), "user-a-token")
        second = await run_turn(service, first, "user-a-token")

        assert second is first
        assert len(harness.created) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_failed_connection_does_not_fall_back_to_previous_identity(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        harness.fail_connect = True
        agent_b = await run_turn(service, agent_a, "user-b-token")

        assert agent_b.mcp_servers == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_server_not_rediscovered_is_dropped(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        harness.discovered = ["mail", "calendar"]
        agent_a = await run_turn(service, new_agent(), "user-a-token")
        harness.discovered = ["mail"]
        agent_b = await run_turn(service, agent_a, "user-b-token")

        assert authorization_by_server(agent_b) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_caller_configured_server_takes_precedence(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        caller_server = FakeStreamableHttpServer(
            {"url": server_url("mail"), "headers": {"Authorization": "Bearer caller-token"}},
            "caller-mail",
            harness,
        )
        agent = Agent(name="test-agent", instructions="Test.", mcp_servers=[caller_server])

        harness.discovered = ["mail", "calendar"]
        agent_a = await run_turn(service, agent, "user-a-token")
        agent_b = await run_turn(service, agent_a, "user-b-token")

        assert agent_b.mcp_servers[0] is caller_server
        assert authorization_by_server(agent_b) == {
            "caller-mail": "Bearer caller-token",
            "calendar": "Bearer user-b-token",
        }


class TestReplacedServerLifecycle:
    """Servers from an earlier turn are closed unless the current turn reuses them."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_replaced_servers_are_closed(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        agent_b = await run_turn(service, agent_a, "user-b-token")

        assert [server.closed for server in agent_a.mcp_servers] == [True]
        assert [server.closed for server in agent_b.mcp_servers] == [False]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_reused_server_is_not_closed(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        first = await run_turn(service, new_agent(), "user-a-token")
        await run_turn(service, first, "user-a-token")

        assert [server.closed for server in first.mcp_servers] == [False]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_discovery_failure_closes_previous_servers(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        harness.fail_discovery = True
        with pytest.raises(RuntimeError, match="discovery failed"):
            await run_turn(service, agent_a, "user-b-token")

        assert [server.closed for server in agent_a.mcp_servers] == [True]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_all_servers_closes_current_servers(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent = await run_turn(service, new_agent(), "user-a-token")
        await service.cleanup_all_servers()

        assert [server.closed for server in agent.mcp_servers] == [True]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_closed_server_is_not_reused(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        first = await run_turn(service, new_agent(), "user-a-token")
        harness.fail_discovery = True
        with pytest.raises(RuntimeError, match="discovery failed"):
            await run_turn(service, first, "user-a-token")
        harness.fail_discovery = False
        third = await run_turn(service, first, "user-a-token")

        assert len(harness.created) == 2
        assert third.mcp_servers == [harness.created[1]]
        assert third.mcp_servers[0].session is not None


class TestDedicatedConnectionTask:
    """SDK-created MCP servers connect and disconnect in a task of their own."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_closing_from_another_task_does_not_cancel_the_user(
        self, transport: FakeTransport
    ) -> None:
        server = _DedicatedTaskMCPServer(params={"url": server_url("mail")}, name="mail")
        connected = asyncio.Event()
        closed = asyncio.Event()

        async def turn_using_server() -> str:
            await server.connect()
            connected.set()
            await closed.wait()
            await asyncio.sleep(0)
            return "finished"

        async def turn_closing_server() -> None:
            await connected.wait()
            await server.cleanup()
            closed.set()

        results = await asyncio.gather(turn_using_server(), turn_closing_server())

        assert results[0] == "finished"
        assert server.cleaned_up_in is server.connected_in
        assert not server.is_open

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rejected_connection_raises_without_cancelling_the_caller(
        self, transport: FakeTransport
    ) -> None:
        transport.rejected_urls.add(server_url("mail"))
        server = _DedicatedTaskMCPServer(params={"url": server_url("mail")}, name="mail")

        with pytest.raises(ConnectionError, match="mail"):
            await server.connect()
        await asyncio.sleep(0)

        assert server.cleaned_up_in is server.connected_in
        assert not server.is_open

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_server_rejecting_the_caller_is_skipped(
        self, discovery: Harness, transport: FakeTransport
    ) -> None:
        transport.rejected_urls.add(server_url("denied"))
        discovery.discovered = ["denied", "mail"]
        service = McpToolRegistrationService()

        agent = await run_turn(service, new_agent(), "user-b-token")
        await asyncio.sleep(0)

        assert authorization_by_server(agent) == {"mail": "Bearer user-b-token"}
        await service.cleanup_all_servers()
        assert not any(server.is_open for server in agent.mcp_servers)


class TestAgentSettingsPreserved:
    """Adding MCP servers keeps the rest of the agent's configuration."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_guardrails_and_handoffs_are_kept(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        helper = Agent(name="helper", instructions="Helps.")
        guardrail = InputGuardrail(
            guardrail_function=lambda context, agent, user_input: GuardrailFunctionOutput(
                output_info=None, tripwire_triggered=False
            )
        )
        agent = Agent(
            name="test-agent",
            instructions="Test.",
            handoffs=[helper],
            input_guardrails=[guardrail],
        )

        result = await run_turn(service, agent, "user-a-token")

        assert result.handoffs == [helper]
        assert result.input_guardrails == [guardrail]
        assert authorization_by_server(result) == {"mail": "Bearer user-a-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_server_order_does_not_force_recreation(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        caller_server = FakeStreamableHttpServer(
            {"url": server_url("custom"), "headers": {}}, "custom", harness
        )
        agent = Agent(name="test-agent", instructions="Test.", mcp_servers=[caller_server])

        first = await run_turn(service, agent, "user-a-token")
        reordered = first.clone(mcp_servers=list(reversed(first.mcp_servers)))
        second = await run_turn(service, reordered, "user-a-token")

        assert second is reordered

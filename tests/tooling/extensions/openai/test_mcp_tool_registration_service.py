# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for how add_tool_servers_to_agent replaces, reuses and closes MCP servers."""

import asyncio
import contextlib
import gc
import importlib
import sys
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from agents import Agent, GuardrailFunctionOutput, InputGuardrail
from agents.mcp import MCPServerStreamableHttp
from agents.run_context import RunContextWrapper
from microsoft_agents_a365.tooling.extensions.openai import McpToolRegistrationService
from microsoft_agents_a365.tooling.extensions.openai.mcp_tool_registration_service import (
    _DedicatedTaskMCPServer,
)
from microsoft_agents_a365.tooling.models import MCPServerConfig

MODULE = "microsoft_agents_a365.tooling.extensions.openai.mcp_tool_registration_service"
openai_service = importlib.import_module(MODULE)


def server_url(name: str) -> str:
    return f"https://mcp.example.com/{name}"


class FakeStreamableHttpServer:
    """Stands in for the SDK's MCP server and records the headers it was created with."""

    def __init__(self, params: dict[str, object], name: str, harness: "Harness") -> None:
        self.params = params
        self.name = name
        self.closed = False
        self.cleanup_calls = 0
        self.session: object | None = None
        self._harness = harness

    async def connect(self) -> None:
        if self.name in self._harness.cancel_connect:
            raise asyncio.CancelledError()
        if self._harness.fail_connect:
            raise ConnectionError("connect failed")
        self.session = object()

    async def cleanup(self) -> None:
        self.cleanup_calls += 1
        self.closed = True
        self.session = None


class Harness:
    """Controls MCP discovery and connections for one test."""

    def __init__(self) -> None:
        self.discovered: list[str] = ["mail"]
        self.fail_connect = False
        self.fail_discovery = False
        self.cancel_discovery = False
        self.cancel_connect: set[str] = set()
        self.created: list[FakeStreamableHttpServer] = []

    async def list_tool_servers(
        self, agentic_app_id: str, auth_token: str, options: object, **kwargs: object
    ) -> list[MCPServerConfig]:
        if self.cancel_discovery:
            raise asyncio.CancelledError()
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
        self.slow_urls: set[str] = set()

    async def connect(self, server: MCPServerStreamableHttp) -> None:
        task_group = anyio.create_task_group()
        await task_group.__aenter__()
        server.test_task_group = task_group
        server.connected_in = asyncio.current_task()
        if server.params["url"] in self.rejected_urls:
            task_group.start_soon(self._reject)
            # Waits for the initialize response; the failed request cancels this task.
            await anyio.sleep(10)
        if server.params["url"] in self.slow_urls:
            await anyio.sleep(0.05)
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


async def collect_garbage() -> None:
    """Collect garbage, then let the event loop close the servers that no agent holds any more."""
    gc.collect()
    await asyncio.sleep(0)
    closing_tasks = set(openai_service._closing_tasks)
    if closing_tasks:
        await asyncio.wait(closing_tasks, timeout=5)


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

        assert [server.closed for server in harness.created] == [True]

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
        # Shares first's server list, so it still holds the server the failed call closes.
        sibling = first.clone()
        harness.fail_discovery = True
        with pytest.raises(RuntimeError, match="discovery failed"):
            await run_turn(service, first, "user-a-token")
        harness.fail_discovery = False
        third = await run_turn(service, sibling, "user-a-token")

        assert len(harness.created) == 2
        assert third.mcp_servers == [harness.created[1]]
        assert third.mcp_servers[0].session is not None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancelled_discovery_closes_previous_servers(self, harness: Harness) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        harness.cancel_discovery = True
        with pytest.raises(asyncio.CancelledError):
            await run_turn(service, agent_a, "user-b-token")

        assert [server.closed for server in harness.created] == [True]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancelled_connection_closes_servers_from_this_and_earlier_calls(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()

        agent_a = await run_turn(service, new_agent(), "user-a-token")
        harness.discovered = ["mail", "calendar"]
        harness.cancel_connect = {"calendar"}
        with pytest.raises(asyncio.CancelledError):
            await run_turn(service, agent_a, "user-b-token")

        # The earlier call's server and the server this call connected before it was cancelled.
        assert [server.name for server in harness.created] == ["mail", "mail", "calendar"]
        assert [server.closed for server in harness.created[:2]] == [True, True]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_failed_call_leaves_the_agent_usable_without_its_closed_servers(
        self, discovery: Harness, transport: FakeTransport
    ) -> None:
        service = McpToolRegistrationService()
        agent = await run_turn(service, new_agent(), "user-a-token")

        discovery.fail_discovery = True
        with pytest.raises(RuntimeError, match="discovery failed"):
            await run_turn(service, agent, "user-b-token")

        assert agent.mcp_servers == []
        assert await agent.get_all_tools(RunContextWrapper(context=None)) == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancelled_connection_removes_closed_servers_from_the_agent(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        agent = await run_turn(service, new_agent(), "user-a-token")

        harness.discovered = ["mail", "calendar"]
        harness.cancel_connect = {"calendar"}
        with pytest.raises(asyncio.CancelledError):
            await run_turn(service, agent, "user-b-token")

        assert agent.mcp_servers == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_failed_call_keeps_caller_servers_and_lists_shared_with_clones(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        caller_server = FakeStreamableHttpServer(
            {"url": server_url("custom"), "headers": {}}, "custom", harness
        )
        base = Agent(name="test-agent", instructions="Test.", mcp_servers=[caller_server])
        first = await run_turn(service, base, "user-a-token")
        personalized = first.clone(instructions="Personalized for user B.")

        harness.cancel_discovery = True
        with pytest.raises(asyncio.CancelledError):
            await run_turn(service, personalized, "user-b-token")

        assert personalized.mcp_servers == [caller_server]
        assert first.mcp_servers == [caller_server, harness.created[0]]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_reused_server_is_closed_by_the_service_that_returned_the_agent(
        self, harness: Harness
    ) -> None:
        first = await run_turn(McpToolRegistrationService(), new_agent(), "user-a-token")
        second_service = McpToolRegistrationService()
        second = await run_turn(second_service, first, "user-a-token")

        await second_service.cleanup_all_servers()

        assert second is first
        assert [server.closed for server in second.mcp_servers] == [True]


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
    async def test_cancelled_connect_closes_the_server_when_it_finishes_connecting(
        self, transport: FakeTransport
    ) -> None:
        transport.slow_urls.add(server_url("mail"))
        server = _DedicatedTaskMCPServer(params={"url": server_url("mail")}, name="mail")

        connecting = asyncio.ensure_future(server.connect())
        await asyncio.sleep(0)
        connecting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await connecting
        await asyncio.wait_for(server._connection_task, timeout=5)

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

        # No server is connected again. The agent gets a list that keeps them open while it's used.
        assert len(harness.created) == 1
        assert {id(server) for server in second.mcp_servers} == {
            id(server) for server in reordered.mcp_servers
        }
        assert all(not server.closed for server in second.mcp_servers)


class TestServersClosedWithTheirAgent:
    """Without cleanup_all_servers(), servers close once no agent that holds them is alive."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_servers_are_closed_when_the_returned_agent_is_collected(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        agent = await run_turn(service, new_agent(), "user-a-token")
        (server,) = harness.created

        del agent
        await collect_garbage()

        assert server.closed
        assert service._connected_servers == []
        await service.cleanup_all_servers()
        assert server.cleanup_calls == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_servers_stay_open_while_a_clone_of_the_agent_is_alive(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        agent = await run_turn(service, new_agent(), "user-a-token")
        personalized = agent.clone(instructions="Personalized for user A.")
        (server,) = harness.created

        del agent
        await collect_garbage()
        assert not server.closed

        del personalized
        await collect_garbage()
        assert server.closed

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_reused_server_stays_open_while_any_agent_holding_it_is_alive(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        first = await run_turn(service, new_agent(), "user-a-token")
        harness.discovered = ["mail", "calendar"]
        second = await run_turn(service, first, "user-a-token")
        mail, calendar = harness.created
        assert second.mcp_servers == [mail, calendar]

        del first
        await collect_garbage()
        assert not mail.closed

        del second
        await collect_garbage()
        assert mail.closed and calendar.closed

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_turns_sharing_a_service_keep_their_own_servers_open(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        agent_a = await run_turn(service, new_agent(), "user-a-token")
        agent_b = await run_turn(service, new_agent(), "user-b-token")
        server_a, server_b = harness.created

        del agent_a
        await collect_garbage()

        assert server_a.closed and not server_b.closed
        assert service._connected_servers == [server_b]
        assert authorization_by_server(agent_b) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_server_is_closed_on_its_loop_when_collected_in_another_thread(
        self, discovery: Harness, transport: FakeTransport
    ) -> None:
        service = McpToolRegistrationService()
        agent = await run_turn(service, new_agent(), "user-a-token")
        (server,) = agent.mcp_servers
        # A reference cycle, so only the cycle collector frees the agent, here in another thread.
        agent.cycle = agent
        del agent

        await asyncio.to_thread(gc.collect)
        await collect_garbage()

        assert not server.is_open
        assert server.cleaned_up_in is server.connected_in

    @pytest.mark.unit
    def test_agent_collected_after_its_event_loop_closed_is_ignored(
        self, harness: Harness, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unraisable: list[object] = []
        monkeypatch.setattr(sys, "unraisablehook", unraisable.append)
        agents: list[Agent] = []

        async def register() -> None:
            agents.append(await run_turn(McpToolRegistrationService(), new_agent(), "user-a-token"))

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(register())
        finally:
            loop.close()
        agents.clear()
        gc.collect()

        assert unraisable == []

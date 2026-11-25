# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests that add_tool_servers_to_agent never leaves another identity's MCP plugin on a kernel."""

import asyncio
import importlib
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents_a365.tooling.extensions.semantickernel import McpToolRegistrationService
from microsoft_agents_a365.tooling.models import MCPServerConfig
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

MODULE = (
    "microsoft_agents_a365.tooling.extensions.semantickernel.services.mcp_tool_registration_service"
)


class FakeMcpPlugin:
    """Stands in for MCPStreamableHttpPlugin; its tool returns the Authorization header it holds."""

    def __init__(self, name: str, url: str, headers: dict[str, str], harness: "Harness") -> None:
        self.name = name
        self.url = url
        self.headers = headers
        self.closed = False
        self.close_calls = 0
        self._harness = harness

    async def connect(self) -> None:
        if self._harness.fail_connect:
            raise ConnectionError("connect failed")

    async def close(self) -> None:
        self.close_calls += 1
        await asyncio.sleep(self._harness.close_delay)
        if self._harness.fail_close:
            raise RuntimeError("close failed")
        self.closed = True

    @kernel_function(name="authorization", description="Returns the Authorization header.")
    def authorization(self) -> str:
        return self.headers["Authorization"]


class ToollessFakeMcpPlugin(FakeMcpPlugin):
    """An MCP plugin for a server without tools or prompts: its kernel plugin has no functions."""

    authorization = None  # type: ignore[assignment]


class StalledFakeMcpPlugin(FakeMcpPlugin):
    """Mimics MCPPluginBase.connect() when the connection fails: the background connection task
    ends without reporting that it is ready, or, as when the transport cannot be created, reports
    ready and then fails, so connect() returns without a connection."""

    async def connect(self) -> None:
        ready = asyncio.Event()

        async def connection() -> None:
            if self._harness.stall_reports_ready:
                ready.set()
            raise self._harness.stall_error("connection failed")

        self._current_task = asyncio.create_task(connection())
        await ready.wait()


class SlowFakeMcpPlugin(FakeMcpPlugin):
    """Mimics MCPPluginBase: connect() waits for a background task that connects, reports ready,
    then holds the connection until close() sets its stop event."""

    closed = False

    async def connect(self) -> None:
        ready = asyncio.Event()
        self._stop_event: asyncio.Event | None = None

        async def connection() -> None:
            await asyncio.sleep(0.05)
            ready.set()
            self._stop_event = asyncio.Event()
            await self._stop_event.wait()
            self.closed = True

        self._current_task = asyncio.create_task(connection())
        await ready.wait()

    async def close(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        await self._current_task


class CallerMathPlugin:
    """A plugin the caller added to the kernel."""

    @kernel_function(name="add", description="Adds two numbers.")
    def add(self, a: int, b: int) -> int:
        return a + b


class Harness:
    """Controls MCP discovery and plugin connections for one test."""

    def __init__(self) -> None:
        self.discovered: list[str] = ["mail"]
        self.fail_connect = False
        self.fail_close = False
        self.close_delay = 0.0
        self.fail_discovery = False
        self.stalled: set[str] = set()
        self.stall_error: type[BaseException] = ConnectionError
        self.stall_reports_ready = False
        self.slow: set[str] = set()
        self.toolless: set[str] = set()
        self.created: list[FakeMcpPlugin] = []

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
                url=f"https://mcp.example.com/{name}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            for name in self.discovered
        ]

    def create_plugin(self, name: str, url: str, headers: dict[str, str]) -> FakeMcpPlugin:
        if name in self.stalled:
            plugin: FakeMcpPlugin = StalledFakeMcpPlugin(name, url, headers, self)
        elif name in self.slow:
            plugin = SlowFakeMcpPlugin(name, url, headers, self)
        elif name in self.toolless:
            plugin = ToollessFakeMcpPlugin(name, url, headers, self)
        else:
            plugin = FakeMcpPlugin(name, url, headers, self)
        self.created.append(plugin)
        return plugin


@pytest.fixture
def harness() -> Iterator[Harness]:
    test_harness = Harness()
    config_service = MagicMock()
    config_service.list_tool_servers = AsyncMock(side_effect=test_harness.list_tool_servers)
    with (
        patch(f"{MODULE}.McpToolServerConfigurationService", return_value=config_service),
        patch(f"{MODULE}.MCPStreamableHttpPlugin", side_effect=test_harness.create_plugin),
        patch(f"{MODULE}.Utility") as utility,
        patch(f"{MODULE}.is_development_environment", return_value=False),
        patch(
            f"{MODULE}.get_mcp_platform_authentication_scope",
            return_value=["https://test.scope/.default"],
        ),
    ):
        utility.resolve_agent_identity.return_value = "agent-123"
        utility.get_user_agent_header.return_value = "Agent365SDK/test"
        yield test_harness


async def run_turn(
    service: McpToolRegistrationService,
    kernel: Kernel,
    token: str | None,
    auth: MagicMock | None = None,
) -> None:
    await service.add_tool_servers_to_agent(
        kernel=kernel,
        auth=auth or MagicMock(),
        auth_handler_name="agentic",
        context=MagicMock(),
        auth_token=token,
    )


async def authorization_by_plugin(kernel: Kernel) -> dict[str, str]:
    """Invoke each MCP plugin's tool to see which token a call would send."""
    result: dict[str, str] = {}
    for name, plugin in kernel.plugins.items():
        if "authorization" in plugin.functions:
            value = await kernel.invoke(plugin_name=name, function_name="authorization")
            result[name] = value.value
    return result


async def finish_closing() -> None:
    """Wait for the MCP plugins the service is closing in the background."""
    closing_tasks = set(importlib.import_module(MODULE)._closing_tasks)
    if closing_tasks:
        await asyncio.wait(closing_tasks, timeout=5)


class TestMcpPluginIdentityIsolation:
    """A reused kernel must only call MCP servers with the current turn's token."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_reused_kernel_gets_current_identity_token(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()

        await run_turn(service, kernel, "user-a-token")
        await run_turn(service, kernel, "user-b-token")

        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_failed_connection_removes_previous_identity_plugin(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()

        await run_turn(service, kernel, "user-a-token")
        harness.fail_connect = True
        await run_turn(service, kernel, "user-b-token")

        assert await authorization_by_plugin(kernel) == {}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_plugin_not_rediscovered_is_removed(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()

        harness.discovered = ["mail", "calendar"]
        await run_turn(service, kernel, "user-a-token")
        harness.discovered = ["mail"]
        await run_turn(service, kernel, "user-b-token")

        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_plugins_from_another_service_instance_are_removed(
        self, harness: Harness
    ) -> None:
        kernel = Kernel()

        harness.discovered = ["mail", "calendar"]
        await run_turn(McpToolRegistrationService(), kernel, "user-a-token")
        harness.discovered = ["mail"]
        await run_turn(McpToolRegistrationService(), kernel, "user-b-token")

        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_caller_plugins_are_kept(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        kernel.add_plugin(CallerMathPlugin(), "math")

        await run_turn(service, kernel, "user-a-token")
        harness.fail_connect = True
        await run_turn(service, kernel, "user-b-token")

        assert list(kernel.plugins) == ["math"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_previous_plugins_removed_when_token_exchange_fails(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        await run_turn(service, kernel, "user-a-token")

        failing_auth = MagicMock()
        failing_auth.exchange_token = AsyncMock(side_effect=RuntimeError("exchange failed"))
        with pytest.raises(RuntimeError, match="exchange failed"):
            await run_turn(service, kernel, None, auth=failing_auth)

        assert await authorization_by_plugin(kernel) == {}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_previous_plugins_removed_when_discovery_fails(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        await run_turn(service, kernel, "user-a-token")

        harness.fail_discovery = True
        with pytest.raises(RuntimeError, match="discovery failed"):
            await run_turn(service, kernel, "user-b-token")

        assert await authorization_by_plugin(kernel) == {}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cloned_kernel_removes_previous_identity_plugin(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        await run_turn(service, kernel, "user-a-token")

        cloned = kernel.clone()
        harness.fail_connect = True
        await run_turn(service, cloned, "user-b-token")

        assert await authorization_by_plugin(cloned) == {}

    @pytest.mark.asyncio
    @pytest.mark.unit
    @pytest.mark.parametrize("stall_error", [ConnectionError, asyncio.CancelledError])
    async def test_server_that_never_finishes_connecting_is_skipped(
        self, harness: Harness, stall_error: type[BaseException]
    ) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        harness.discovered = ["denied", "mail"]
        harness.stalled = {"denied"}
        harness.stall_error = stall_error

        await asyncio.wait_for(run_turn(service, kernel, "user-b-token"), timeout=5)

        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_server_whose_connection_fails_after_reporting_ready_is_skipped(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        harness.discovered = ["denied", "mail"]
        harness.stalled = {"denied"}
        harness.stall_reports_ready = True

        await asyncio.wait_for(run_turn(service, kernel, "user-b-token"), timeout=5)

        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancelled_registration_closes_a_plugin_that_is_still_connecting(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        harness.slow = {"mail"}

        turn = asyncio.ensure_future(run_turn(service, Kernel(), "user-b-token"))
        await asyncio.sleep(0.01)
        turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await turn
        plugin = harness.created[0]
        await asyncio.wait_for(plugin._current_task, timeout=5)

        assert plugin.closed


class TestReplacedPluginLifecycle:
    """MCP plugins that a later call replaces are closed and no longer tracked."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_replaced_plugins_are_closed_and_released(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()

        await run_turn(service, kernel, "user-a-token")
        await run_turn(service, kernel, "user-b-token")
        await finish_closing()

        replaced, current = harness.created
        assert replaced.closed and not current.closed
        assert service._connected_plugins == [current]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_waits_for_replaced_plugins_to_close(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        harness.close_delay = 0.05
        await run_turn(service, kernel, "user-a-token")
        await run_turn(service, kernel, "user-b-token")
        replaced, current = harness.created
        assert service._connected_plugins == [current]

        await service.cleanup_connections()

        assert replaced.closed and current.closed
        assert [replaced.close_calls, current.close_calls] == [1, 1]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_plugins_shared_with_a_kernel_clone_are_closed_when_replaced(
        self, harness: Harness
    ) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        await run_turn(service, kernel, "user-a-token")

        await run_turn(service, kernel.clone(), "user-b-token")
        await finish_closing()

        assert [plugin.closed for plugin in harness.created] == [True, False]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_plugin_without_functions_is_closed_when_replaced(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        harness.discovered = ["empty"]
        harness.toolless = {"empty"}

        await run_turn(service, kernel, "user-a-token")
        await run_turn(service, kernel, "user-b-token")
        await finish_closing()

        assert list(kernel.plugins) == ["empty"]
        assert [plugin.closed for plugin in harness.created] == [True, False]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_failing_close_does_not_fail_the_call(self, harness: Harness) -> None:
        service = McpToolRegistrationService()
        kernel = Kernel()
        await run_turn(service, kernel, "user-a-token")
        harness.fail_close = True

        await run_turn(service, kernel, "user-b-token")
        await finish_closing()

        assert harness.created[0].close_calls == 1
        assert await authorization_by_plugin(kernel) == {"mail": "Bearer user-b-token"}

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from microsoft_agents_a365.runtime.third_party_connect import (
    Connection,
    ConnectionRequest,
    DiscoveredAgent,
    DiscoveryPage,
    ImportedAgent,
    TelemetrySyncResult,
    ThirdPartyConnectRuntime,
)


class DemoConnections:
    async def create(self, request: ConnectionRequest) -> Connection:
        return Connection("demo-connection", request.provider)


class DemoAwsRuntime:
    def __init__(self) -> None:
        self.discovery_calls: list[str | None] = []

    async def discover_agents(
        self, connection: Connection, continuation_token: str | None
    ) -> DiscoveryPage:
        self.discovery_calls.append(continuation_token)
        if continuation_token is None:
            return DiscoveryPage(
                (
                    DiscoveredAgent("aws-agent-1", "Support Assistant"),
                    DiscoveredAgent("aws-agent-2", "Research Assistant"),
                ),
                "page-2",
            )
        return DiscoveryPage(
            (
                DiscoveredAgent("aws-agent-2", "Research Assistant"),
                DiscoveredAgent("aws-agent-3", "Operations Assistant"),
            )
        )

    async def sync_telemetry(
        self, connection: Connection, agents: tuple[ImportedAgent, ...]
    ) -> TelemetrySyncResult:
        return TelemetrySyncResult(len(agents) * 2, len(agents) * 2, "checkpoint-1")


class DemoRegistry:
    async def import_agents(
        self, connection: Connection, agents: tuple[DiscoveredAgent, ...]
    ) -> tuple[ImportedAgent, ...]:
        return tuple(
            ImportedAgent(agent.provider_agent_id, f"a365-{agent.provider_agent_id}")
            for agent in agents
        )


@pytest.mark.asyncio
async def test_connect_imports_all_pages_and_syncs_telemetry() -> None:
    provider = DemoAwsRuntime()
    runtime = ThirdPartyConnectRuntime(
        DemoConnections(), {"aws": provider}, DemoRegistry()
    )

    result = await runtime.connect(ConnectionRequest("aws", "Demo AWS"))

    assert result.connection.connection_id == "demo-connection"
    assert result.discovered_agents == 3
    assert len(result.imported_agents) == 3
    assert result.telemetry.records_exported == 6
    assert result.telemetry.checkpoint == "checkpoint-1"
    assert provider.discovery_calls == [None, "page-2"]
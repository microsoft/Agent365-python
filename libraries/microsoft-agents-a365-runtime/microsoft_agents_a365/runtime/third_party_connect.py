# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ConnectionRequest:
    provider: str
    name: str
    configuration: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Connection:
    connection_id: str
    provider: str


@dataclass(frozen=True)
class DiscoveredAgent:
    provider_agent_id: str
    display_name: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryPage:
    agents: tuple[DiscoveredAgent, ...]
    continuation_token: str | None = None


@dataclass(frozen=True)
class ImportedAgent:
    provider_agent_id: str
    observability_id: str


@dataclass(frozen=True)
class TelemetrySyncResult:
    records_read: int
    records_exported: int
    checkpoint: str | None = None


@dataclass(frozen=True)
class ConnectResult:
    connection: Connection
    discovered_agents: int
    imported_agents: tuple[ImportedAgent, ...]
    telemetry: TelemetrySyncResult


class ConnectionClient(Protocol):
    async def create(self, request: ConnectionRequest) -> Connection: ...


class ProviderRuntime(Protocol):
    async def discover_agents(
        self, connection: Connection, continuation_token: str | None
    ) -> DiscoveryPage: ...

    async def sync_telemetry(
        self, connection: Connection, agents: tuple[ImportedAgent, ...]
    ) -> TelemetrySyncResult: ...


class RegistryClient(Protocol):
    async def import_agents(
        self, connection: Connection, agents: tuple[DiscoveredAgent, ...]
    ) -> tuple[ImportedAgent, ...]: ...


class ThirdPartyConnectRuntime:
    """Runs one connection through discovery, Registry import, and telemetry sync."""

    def __init__(
        self,
        connections: ConnectionClient,
        providers: dict[str, ProviderRuntime],
        registry: RegistryClient,
    ) -> None:
        self._connections = connections
        self._providers = providers
        self._registry = registry

    async def connect(self, request: ConnectionRequest) -> ConnectResult:
        provider = self._providers.get(request.provider.casefold())
        if provider is None:
            raise ValueError(f"Unsupported provider: {request.provider}")

        connection = await self._connections.create(request)
        discovered: list[DiscoveredAgent] = []
        continuation_token: str | None = None
        seen_tokens: set[str] = set()

        while True:
            page = await provider.discover_agents(connection, continuation_token)
            discovered.extend(page.agents)
            continuation_token = page.continuation_token
            if continuation_token is None:
                break
            if continuation_token in seen_tokens:
                raise RuntimeError("Provider returned a repeated discovery continuation token")
            seen_tokens.add(continuation_token)

        unique_agents = tuple(
            {agent.provider_agent_id: agent for agent in discovered}.values()
        )
        imported = await self._registry.import_agents(connection, unique_agents)
        telemetry = await provider.sync_telemetry(connection, imported)
        return ConnectResult(connection, len(unique_agents), imported, telemetry)
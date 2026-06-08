# MCP Connection-Gated Tool Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block agent execution when a configured MCP server reports `connectivityStatus: "Pending"`, raising a typed error carrying the connection-setup URLs so the agent's turn handler can prompt the user instead of running tools that would fail.

**Architecture:** Extend `MCPServerConfig` with the new per-server connection fields; capture the response-level (aggregate) connection metadata into a new internal `McpDiscoveryResult`; in core `McpToolServerConfigurationService.list_tool_servers`, raise `McpConnectionsRequiredError` when the aggregate status is present and not `"Ready"`. Dev-mode manifests and legacy raw-array responses omit the field → never gated. Framework extensions let the exception propagate to the turn handler.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, `ruff`. Package: `microsoft-agents-a365-tooling`.

**Spec:** `docs/superpowers/specs/2026-06-08-mcp-connection-gating-design.md`

---

## Background / orientation (read once)

Key file: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py`

Relevant existing flow inside `list_tool_servers`:
- Dev: `servers = self._load_servers_from_manifest()` (returns `List[MCPServerConfig]`).
- Prod: `discovery = await self._load_servers_from_gateway(...)` then either OBO token
  acquirer or a legacy V2-guard early-return.
- Both end with `_attach_per_audience_tokens(...)` then `return servers`.

Parsing helpers:
- `_parse_server_config(server_element)` — maps one JSON object (gateway **or** manifest)
  to `MCPServerConfig`. Lines ~685–741.
- `_parse_gateway_response(response)` — currently returns `List[MCPServerConfig]`;
  handles wrapped `{"mcpServers": [...]}` and legacy raw-array shapes. Lines ~639–679.

**Gate placement decision (refinement over spec wording):** enforce the gate in
`list_tool_servers` immediately after the gateway discovery call returns, *before* token
attachment and before the auth-context branching. Connection readiness is independent of
token exchange, so gating first also avoids unnecessary OBO exchanges when connections
aren't ready. The dev/manifest path is never gated (no aggregate field).

**Conventions to follow:**
- Copyright header on every `.py` file (ruff `CPY` rule):
  ```python
  # Copyright (c) Microsoft Corporation.
  # Licensed under the MIT License.
  ```
- Type hints on all params/returns. Never use `typing.Any`. Use `is not None` for None checks.
- Run tests: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py -v`
- Lint/format: `uv run --frozen ruff check .` and `uv run --frozen ruff format .`

---

## File Structure

- **Modify** `.../tooling/models/mcp_server_config.py` — add 4 optional fields.
- **Create** `.../tooling/exceptions.py` — `McpConnectionsRequiredError`.
- **Modify** `.../tooling/__init__.py` — export the exception.
- **Modify** `.../tooling/services/mcp_tool_server_configuration_service.py` — add
  `McpDiscoveryResult`, per-server field parsing, aggregate parsing, gate enforcement.
- **Modify** `tests/tooling/test_mcp_server_configuration.py` — new tests.
- **Create** `tests/tooling/test_mcp_connections_required_error.py` — exception tests.
- **Modify** `.../tooling/CHANGELOG.md` — changelog entry.
- **Modify** `.../tooling/docs/design.md` — document the catch-and-reply pattern.

Path prefix for all `.../tooling/...` entries:
`libraries/microsoft-agents-a365-tooling/microsoft_agents_a365`

---

## Task 1: Add connection fields to `MCPServerConfig`

**Files:**
- Modify: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/models/mcp_server_config.py`
- Test: `tests/tooling/test_mcp_server_configuration.py`

- [ ] **Step 1: Write the failing test**

Add to class `TestMCPServerConfig` in `tests/tooling/test_mcp_server_configuration.py`:

```python
    def test_mcp_server_config_connection_fields_default_none(self):
        """Connection fields default to None for backward compatibility."""
        config = MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
        )
        assert config.id is None
        assert config.all_connections_url is None
        assert config.missing_connections_url is None
        assert config.connectivity_status is None

    def test_mcp_server_config_connection_fields_set(self):
        """Connection fields are stored when provided."""
        config = MCPServerConfig(
            mcp_server_name="TestServer",
            mcp_server_unique_name="test_server",
            id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            all_connections_url="https://make.example/all",
            missing_connections_url="https://make.example/missing",
            connectivity_status="Pending",
        )
        assert config.id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert config.all_connections_url == "https://make.example/all"
        assert config.missing_connections_url == "https://make.example/missing"
        assert config.connectivity_status == "Pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestMCPServerConfig::test_mcp_server_config_connection_fields_set -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'id'`.

- [ ] **Step 3: Add the fields to the dataclass**

In `mcp_server_config.py`, add these fields inside the `MCPServerConfig` dataclass,
after the existing `publisher` field (keep all new fields optional with `None` defaults):

```python
    #: Unique identifier (GUID) of the MCP server from the gateway, if provided.
    id: Optional[str] = None

    #: Per-server URL to view/manage all connections for this server's connector.
    all_connections_url: Optional[str] = None

    #: Per-server URL to set up the connections this server is missing.
    missing_connections_url: Optional[str] = None

    #: Per-server connectivity status reported by the gateway ("Ready" or "Pending").
    #: None when the source predates the field (dev manifest / legacy raw-array gateway).
    connectivity_status: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestMCPServerConfig -v`
Expected: PASS (all tests in the class).

- [ ] **Step 5: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/models/mcp_server_config.py tests/tooling/test_mcp_server_configuration.py
git commit -m "feat(tooling): add connection fields to MCPServerConfig

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Add `McpConnectionsRequiredError` exception

**Files:**
- Create: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/exceptions.py`
- Modify: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/__init__.py`
- Test: `tests/tooling/test_mcp_connections_required_error.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tooling/test_mcp_connections_required_error.py`:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for McpConnectionsRequiredError."""

from microsoft_agents_a365.tooling import McpConnectionsRequiredError


def test_exception_exposes_payload():
    err = McpConnectionsRequiredError(
        missing_connections_url="https://make.example/missing",
        all_connections_url="https://make.example/all",
        connectivity_status="Pending",
        server_names=["mcp_Salesforce", "mcp_Zendesk"],
    )
    assert err.missing_connections_url == "https://make.example/missing"
    assert err.all_connections_url == "https://make.example/all"
    assert err.connectivity_status == "Pending"
    assert err.server_names == ["mcp_Salesforce", "mcp_Zendesk"]


def test_exception_message_is_actionable():
    err = McpConnectionsRequiredError(
        missing_connections_url="https://make.example/missing",
        all_connections_url=None,
        connectivity_status="Pending",
        server_names=["mcp_Salesforce"],
    )
    message = str(err)
    assert "mcp_Salesforce" in message
    assert "https://make.example/missing" in message


def test_exception_is_exception_subclass():
    assert issubclass(McpConnectionsRequiredError, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/tooling/test_mcp_connections_required_error.py -v`
Expected: FAIL with `ImportError: cannot import name 'McpConnectionsRequiredError'`.

- [ ] **Step 3: Create the exception module**

Create `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/exceptions.py`:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Exceptions raised by the MCP tooling layer."""

from typing import List, Optional


class McpConnectionsRequiredError(Exception):
    """Raised when one or more configured MCP servers are not yet connection-ready.

    The tooling gateway reports an aggregate ``connectivityStatus`` of ``"Pending"``
    when the agent's MCP servers have downstream connections that the user has not yet
    established. The agent's turn handler should catch this error, reply to the user
    with ``missing_connections_url``, and return without running the model/tools.
    A later turn re-runs discovery and proceeds once the connections are in place.
    """

    def __init__(
        self,
        missing_connections_url: Optional[str],
        all_connections_url: Optional[str],
        connectivity_status: Optional[str],
        server_names: List[str],
    ) -> None:
        self.missing_connections_url = missing_connections_url
        self.all_connections_url = all_connections_url
        self.connectivity_status = connectivity_status
        self.server_names = server_names
        servers_text = ", ".join(server_names) if server_names else "(unknown)"
        super().__init__(
            f"MCP servers [{servers_text}] require connection setup "
            f"(connectivityStatus={connectivity_status}). "
            f"Set up missing connections at: {missing_connections_url}"
        )
```

- [ ] **Step 4: Export from the package `__init__`**

In `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/__init__.py`,
add the import after the existing `from .services import ...` line:

```python
from .exceptions import McpConnectionsRequiredError
```

and add `"McpConnectionsRequiredError"` to the `__all__` list (place it after
`"McpToolServerConfigurationService"`).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --frozen pytest tests/tooling/test_mcp_connections_required_error.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/exceptions.py libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/__init__.py tests/tooling/test_mcp_connections_required_error.py
git commit -m "feat(tooling): add McpConnectionsRequiredError

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Parse per-server connection fields in `_parse_server_config`

**Files:**
- Modify: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py`
- Test: `tests/tooling/test_mcp_server_configuration.py`

- [ ] **Step 1: Write the failing test**

Add to class `TestMcpToolServerConfigurationService` in
`tests/tooling/test_mcp_server_configuration.py`:

```python
    def test_parse_server_config_populates_connection_fields(self, service):
        """Per-server connection fields are parsed from a V2 gateway element."""
        server_element = {
            "mcpServerName": "mcp_Salesforce",
            "mcpServerUniqueName": "mcp_Salesforce",
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "url": "https://gw.example/agents/v2/servers/mcp_Salesforce",
            "allConnectionsUrl": "https://make.example/all",
            "missingConnectionsUrl": "https://make.example/missing",
            "connectivityStatus": "Pending",
        }

        config = service._parse_server_config(server_element)

        assert config is not None
        assert config.id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert config.all_connections_url == "https://make.example/all"
        assert config.missing_connections_url == "https://make.example/missing"
        assert config.connectivity_status == "Pending"

    def test_parse_server_config_connection_fields_absent(self, service):
        """Manifest elements without connection fields yield None."""
        server_element = {
            "mcpServerName": "DevServer",
            "mcpServerUniqueName": "dev_server",
            "url": "https://dev.server/mcp",
        }

        config = service._parse_server_config(server_element)

        assert config is not None
        assert config.id is None
        assert config.all_connections_url is None
        assert config.missing_connections_url is None
        assert config.connectivity_status is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestMcpToolServerConfigurationService::test_parse_server_config_populates_connection_fields -v`
Expected: FAIL with `AssertionError` (e.g. `config.id` is `None`, not the GUID).

- [ ] **Step 3: Map the new fields in `_parse_server_config`**

In `mcp_tool_server_configuration_service.py`, inside `_parse_server_config`, locate the
`return MCPServerConfig(...)` call (around line 728). Immediately **before** that return,
add string-or-None extraction for the four fields:

```python
            id_raw = server_element.get("id")
            server_id = str(id_raw) if id_raw is not None else None

            all_conn_raw = server_element.get("allConnectionsUrl")
            all_connections_url = str(all_conn_raw) if all_conn_raw is not None else None

            missing_conn_raw = server_element.get("missingConnectionsUrl")
            missing_connections_url = (
                str(missing_conn_raw) if missing_conn_raw is not None else None
            )

            status_raw = server_element.get("connectivityStatus")
            connectivity_status = str(status_raw) if status_raw is not None else None
```

Then extend the `return MCPServerConfig(...)` call to pass them:

```python
            return MCPServerConfig(
                mcp_server_name=mcp_server_name,
                mcp_server_unique_name=mcp_server_unique_name,
                url=final_url,
                audience=audience,
                scope=scope,
                publisher=publisher,
                id=server_id,
                all_connections_url=all_connections_url,
                missing_connections_url=missing_connections_url,
                connectivity_status=connectivity_status,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestMcpToolServerConfigurationService -v -k parse_server_config`
Expected: PASS (the two new tests plus the existing `_parse_server_config` tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py tests/tooling/test_mcp_server_configuration.py
git commit -m "feat(tooling): parse per-server MCP connection fields

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Capture aggregate metadata via `McpDiscoveryResult`

This task adds the internal result wrapper and makes `_parse_gateway_response` /
`_load_servers_from_gateway` carry the response-level (aggregate) connection fields.
`list_tool_servers` is updated to unwrap `.servers` so external behavior is unchanged.

**Files:**
- Modify: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py`
- Test: `tests/tooling/test_mcp_server_configuration.py`

- [ ] **Step 1: Write the failing test**

Add to class `TestMcpToolServerConfigurationService`:

```python
    @pytest.mark.asyncio
    async def test_parse_gateway_response_captures_aggregate(self, service):
        """Response-level connection metadata is captured into McpDiscoveryResult."""
        payload = {
            "mcpServers": [
                {
                    "mcpServerName": "mcp_Salesforce",
                    "mcpServerUniqueName": "mcp_Salesforce",
                    "url": "https://gw.example/agents/v2/servers/mcp_Salesforce",
                    "connectivityStatus": "Pending",
                }
            ],
            "allConnectionsUrl": "https://make.example/all",
            "missingConnectionsUrl": "https://make.example/missing",
            "connectivityStatus": "Pending",
        }
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=payload)

        result = await service._parse_gateway_response(mock_response)

        assert len(result.servers) == 1
        assert result.servers[0].mcp_server_name == "mcp_Salesforce"
        assert result.all_connections_url == "https://make.example/all"
        assert result.missing_connections_url == "https://make.example/missing"
        assert result.connectivity_status == "Pending"

    @pytest.mark.asyncio
    async def test_parse_gateway_response_raw_array_has_no_aggregate(self, service):
        """Legacy raw-array responses produce a result with aggregate fields None."""
        payload = [
            {
                "mcpServerName": "V1Server",
                "mcpServerUniqueName": "v1_server",
                "url": "https://v1.example.com/mcp",
            }
        ]
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=payload)

        result = await service._parse_gateway_response(mock_response)

        assert len(result.servers) == 1
        assert result.all_connections_url is None
        assert result.missing_connections_url is None
        assert result.connectivity_status is None
```

(`MagicMock` and `AsyncMock` are already imported at the top of the test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestMcpToolServerConfigurationService::test_parse_gateway_response_captures_aggregate -v`
Expected: FAIL with `AttributeError: 'list' object has no attribute 'servers'` (current
return is a list).

- [ ] **Step 3: Define `McpDiscoveryResult`**

In `mcp_tool_server_configuration_service.py`, ensure `dataclass` is imported. The module
already has `from dataclasses import replace as dataclass_replace`; add a second import
line directly above it:

```python
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
```

Then, in the `# TYPES` section (just below the `TokenAcquirer` definition near line 62),
add:

```python
@dataclass
class McpDiscoveryResult:
    """Internal result of MCP server discovery from the gateway.

    Carries the parsed server list plus the response-level (aggregate) connection
    metadata used for connection gating. Sources that predate the connection fields
    (legacy raw-array gateway responses, dev-mode manifests) leave the aggregate
    fields as ``None``.
    """

    servers: List["MCPServerConfig"]
    all_connections_url: Optional[str] = None
    missing_connections_url: Optional[str] = None
    connectivity_status: Optional[str] = None
```

- [ ] **Step 4: Update `_parse_gateway_response` to return `McpDiscoveryResult`**

Replace the entire body of `_parse_gateway_response` (the method around lines 639–679) so
it returns a `McpDiscoveryResult`. Keep the existing wrapped/raw-array branching; add
aggregate extraction for the wrapped shape:

```python
    async def _parse_gateway_response(
        self, response: aiohttp.ClientResponse
    ) -> McpDiscoveryResult:
        """
        Parses the response from the tooling gateway.

        Supports two response shapes:
        - Wrapped: ``{"mcpServers": [...], "connectivityStatus": ..., ...}``
        - Raw array: ``[...]`` (legacy V1 gateway format, no aggregate metadata)

        Args:
            response: HTTP response from the gateway.

        Returns:
            McpDiscoveryResult: parsed servers plus response-level connection metadata
            (aggregate fields are None for the legacy raw-array shape).
        """
        config_data = await response.json(content_type=None)

        server_elements: Optional[List[object]] = None
        all_connections_url: Optional[str] = None
        missing_connections_url: Optional[str] = None
        connectivity_status: Optional[str] = None

        if isinstance(config_data, list):
            # Raw array format (legacy V1 gateway returns bare array, no aggregate).
            self._logger.debug("Gateway returned raw array response")
            server_elements = config_data
        elif isinstance(config_data, dict) and isinstance(config_data.get("mcpServers"), list):
            # Wrapped format: {"mcpServers": [...], aggregate connection fields}
            self._logger.debug("Gateway returned wrapped mcpServers response")
            server_elements = config_data["mcpServers"]

            all_raw = config_data.get("allConnectionsUrl")
            all_connections_url = str(all_raw) if all_raw is not None else None

            missing_raw = config_data.get("missingConnectionsUrl")
            missing_connections_url = str(missing_raw) if missing_raw is not None else None

            status_raw = config_data.get("connectivityStatus")
            connectivity_status = str(status_raw) if status_raw is not None else None
        else:
            self._logger.warning(
                'Unexpected gateway response format: expected a list or {"mcpServers": [...]}'
            )
            return McpDiscoveryResult(servers=[])

        mcp_servers: List[MCPServerConfig] = []
        for server_element in server_elements:
            if isinstance(server_element, dict):
                server_config = self._parse_server_config(server_element)
                if server_config is not None:
                    mcp_servers.append(server_config)

        return McpDiscoveryResult(
            servers=mcp_servers,
            all_connections_url=all_connections_url,
            missing_connections_url=missing_connections_url,
            connectivity_status=connectivity_status,
        )
```

- [ ] **Step 5: Update `_load_servers_from_gateway` to return `McpDiscoveryResult`**

In `_load_servers_from_gateway` (around lines 485–537), change the return type annotation
from `List[MCPServerConfig]` to `McpDiscoveryResult`, and update the success branch.
Locate:

```python
                    if response.status == 200:
                        mcp_servers = await self._parse_gateway_response(response)
                        self._logger.info(
                            f"Retrieved {len(mcp_servers)} MCP tool servers from tooling gateway"
                        )
                        return mcp_servers
```

Replace with:

```python
                    if response.status == 200:
                        discovery = await self._parse_gateway_response(response)
                        self._logger.info(
                            f"Retrieved {len(discovery.servers)} MCP tool servers "
                            f"from tooling gateway"
                        )
                        return discovery
```

Also change the method signature return annotation line from:

```python
    ) -> List[MCPServerConfig]:
```
to:
```python
    ) -> McpDiscoveryResult:
```

- [ ] **Step 6: Update `list_tool_servers` prod branch to unwrap `.servers`**

In `list_tool_servers`, the production branch currently is:

```python
        else:
            servers = await self._load_servers_from_gateway(
                agentic_app_id, auth_token, options, turn_context
            )
```

Replace with:

```python
        else:
            discovery = await self._load_servers_from_gateway(
                agentic_app_id, auth_token, options, turn_context
            )
            servers = discovery.servers
```

(The gate is added in Task 5 — for now we just unwrap so existing behavior is preserved.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py -v`
Expected: PASS — the two new aggregate tests pass and all pre-existing tests still pass
(production `list_tool_servers` tests continue to work because `.servers` is unwrapped).

- [ ] **Step 8: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py tests/tooling/test_mcp_server_configuration.py
git commit -m "feat(tooling): capture aggregate connection metadata via McpDiscoveryResult

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Enforce the connection-readiness gate in `list_tool_servers`

**Files:**
- Modify: `libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py`
- Test: `tests/tooling/test_mcp_server_configuration.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class to `tests/tooling/test_mcp_server_configuration.py`. The
`_gateway_response` helper builds the nested aiohttp mock used elsewhere in this file.

```python
class TestConnectionGating:
    """Tests for the connectivityStatus connection-readiness gate."""

    @pytest.fixture
    def service(self):
        return McpToolServerConfigurationService()

    @staticmethod
    def _gateway_response(payload):
        """Build a patched aiohttp.ClientSession context manager returning payload."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response_cm = MagicMock()
        mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response_cm)
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        return patch("aiohttp.ClientSession", return_value=mock_session_cm)

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_gate_raises_when_pending(self, service):
        from microsoft_agents_a365.tooling import McpConnectionsRequiredError

        payload = {
            "mcpServers": [
                {
                    "mcpServerName": "mcp_Salesforce",
                    "mcpServerUniqueName": "mcp_Salesforce",
                    "url": "https://gw.example/mcp_Salesforce",
                    "connectivityStatus": "Pending",
                }
            ],
            "allConnectionsUrl": "https://make.example/all",
            "missingConnectionsUrl": "https://make.example/missing",
            "connectivityStatus": "Pending",
        }
        with self._gateway_response(payload):
            with pytest.raises(McpConnectionsRequiredError) as exc_info:
                await service.list_tool_servers(
                    agentic_app_id="test-app-id", auth_token="test-token"
                )
        err = exc_info.value
        assert err.connectivity_status == "Pending"
        assert err.missing_connections_url == "https://make.example/missing"
        assert err.all_connections_url == "https://make.example/all"
        assert "mcp_Salesforce" in err.server_names

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_gate_passes_when_ready(self, service):
        payload = {
            "mcpServers": [
                {
                    "mcpServerName": "mcp_Salesforce",
                    "mcpServerUniqueName": "mcp_Salesforce",
                    "url": "https://gw.example/mcp_Salesforce",
                    "connectivityStatus": "Ready",
                }
            ],
            "allConnectionsUrl": "https://make.example/all",
            "missingConnectionsUrl": "https://make.example/missing",
            "connectivityStatus": "Ready",
        }
        with self._gateway_response(payload):
            servers = await service.list_tool_servers(
                agentic_app_id="test-app-id", auth_token="test-token"
            )
        assert len(servers) == 1
        assert servers[0].mcp_server_name == "mcp_Salesforce"

    @patch.dict(os.environ, {"ENVIRONMENT": "Production"})
    @pytest.mark.asyncio
    async def test_gate_passes_for_legacy_raw_array(self, service):
        payload = [
            {
                "mcpServerName": "V1Server",
                "mcpServerUniqueName": "v1_server",
                "url": "https://v1.example.com/mcp",
            }
        ]
        with self._gateway_response(payload):
            servers = await service.list_tool_servers(
                agentic_app_id="test-app-id", auth_token="test-token"
            )
        assert len(servers) == 1
        assert servers[0].mcp_server_name == "V1Server"

    @patch.object(McpToolServerConfigurationService, "_load_servers_from_manifest")
    @patch.dict(os.environ, {"ENVIRONMENT": "Development"})
    @pytest.mark.asyncio
    async def test_gate_not_applied_in_dev_mode(self, mock_load_manifest, service):
        mock_load_manifest.return_value = [
            MCPServerConfig(
                mcp_server_name="DevServer",
                mcp_server_unique_name="dev_server",
                url="https://dev.server/mcp",
            )
        ]
        servers = await service.list_tool_servers(
            agentic_app_id="test-app-id", auth_token="test-token"
        )
        assert len(servers) == 1
        assert servers[0].mcp_server_name == "DevServer"
```

(`MagicMock`, `AsyncMock`, `patch`, `os`, and `pytest` are already imported at the top of
the existing test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestConnectionGating -v`
Expected: `test_gate_raises_when_pending` FAILS (no exception raised — gate not yet
implemented); the other three may pass already.

- [ ] **Step 3: Import the exception in the service module**

In `mcp_tool_server_configuration_service.py`, with the other local imports (near the
`from ..models import ...` / `from ..utils import Constants` block), add:

```python
from ..exceptions import McpConnectionsRequiredError
```

- [ ] **Step 4: Add the gate helper method**

Add a private method to `McpToolServerConfigurationService` (place it just after
`list_tool_servers`, before the `# ENVIRONMENT DETECTION` section comment):

```python
    # Sentinel aggregate status that means all connections are satisfied.
    _CONNECTIVITY_READY = "Ready"

    def _enforce_connection_readiness(self, discovery: "McpDiscoveryResult") -> None:
        """Raise if the aggregate connectivity status indicates missing connections.

        Blocks only when the response-level ``connectivity_status`` is present and not
        ``"Ready"`` (i.e. ``"Pending"``). Absent status (legacy raw-array gateway
        responses, dev-mode manifests) is always treated as ready, so those paths are
        never gated. The ``!= "Ready"`` form is intentionally defensive against any
        unexpected future status value.

        Raises:
            McpConnectionsRequiredError: when connections are not yet ready.
        """
        status = discovery.connectivity_status
        if status is None or status == self._CONNECTIVITY_READY:
            return

        not_ready = [
            s
            for s in discovery.servers
            if s.connectivity_status is not None
            and s.connectivity_status != self._CONNECTIVITY_READY
        ]
        server_names = [
            s.mcp_server_name or s.mcp_server_unique_name for s in not_ready
        ]
        self._logger.info(
            f"MCP connection gate blocking turn: connectivityStatus={status}, "
            f"servers={server_names}"
        )
        raise McpConnectionsRequiredError(
            missing_connections_url=discovery.missing_connections_url,
            all_connections_url=discovery.all_connections_url,
            connectivity_status=status,
            server_names=server_names,
        )
```

- [ ] **Step 5: Call the gate from the prod branch of `list_tool_servers`**

Update the production branch added in Task 4 to enforce the gate immediately after
discovery, before token branching:

```python
        else:
            discovery = await self._load_servers_from_gateway(
                agentic_app_id, auth_token, options, turn_context
            )
            # Gate execution when configured MCP servers are not connection-ready.
            # Runs before token attachment because readiness is independent of tokens.
            self._enforce_connection_readiness(discovery)
            servers = discovery.servers
```

- [ ] **Step 6: Run the gate tests to verify they pass**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py::TestConnectionGating -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full tooling test module**

Run: `uv run --frozen pytest tests/tooling/test_mcp_server_configuration.py -v`
Expected: PASS (all tests, including pre-existing).

- [ ] **Step 8: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py tests/tooling/test_mcp_server_configuration.py
git commit -m "feat(tooling): gate tool discovery on MCP connectivityStatus

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Documentation and changelog

**Files:**
- Modify: `libraries/microsoft-agents-a365-tooling/CHANGELOG.md`
- Modify: `libraries/microsoft-agents-a365-tooling/docs/design.md`

- [ ] **Step 1: Add CHANGELOG entries**

In `libraries/microsoft-agents-a365-tooling/CHANGELOG.md`, under
`## [Unreleased]` → `### Added`, append these bullets:

```markdown
- Added connection-readiness gating to `McpToolServerConfigurationService.list_tool_servers()`. When the tooling gateway reports an aggregate `connectivityStatus` of `"Pending"`, a `McpConnectionsRequiredError` is raised carrying the response-level `missingConnectionsUrl` / `allConnectionsUrl` and the names of the not-`Ready` servers, so the agent's turn handler can prompt the user to set up connections instead of running tools that would fail. Dev-mode manifests and legacy raw-array gateway responses omit the field and are never gated
- Added `McpConnectionsRequiredError` exception (exported from `microsoft_agents_a365.tooling`) with `missing_connections_url`, `all_connections_url`, `connectivity_status`, and `server_names` attributes
- Added `id`, `all_connections_url`, `missing_connections_url`, and `connectivity_status` fields to `MCPServerConfig`, parsed from the per-server gateway payload
- Added internal `McpDiscoveryResult` dataclass; `_parse_gateway_response()` and `_load_servers_from_gateway()` now return it to carry response-level connection metadata alongside the server list (the public return type of `list_tool_servers()` remains `List[MCPServerConfig]`)
```

- [ ] **Step 2: Document the catch-and-reply pattern in design.md**

In `libraries/microsoft-agents-a365-tooling/docs/design.md`, add a new subsection (place
it after the existing `list_tool_servers` documentation, around line 227). Use this
content:

````markdown
### Connection gating

When the tooling gateway reports that an agent's MCP servers have unsatisfied downstream
connections, `list_tool_servers()` raises `McpConnectionsRequiredError`. Discovery runs
every turn, so the agent's turn handler should catch the error, reply with the
connection-setup link, and return — a later turn proceeds automatically once the user has
connected.

```python
from microsoft_agents_a365.tooling import McpConnectionsRequiredError

try:
    servers = await config_service.list_tool_servers(
        agentic_app_id=agentic_app_id,
        auth_token=auth_token,
        authorization=auth,
        auth_handler_name=auth_handler_name,
        turn_context=context,
    )
except McpConnectionsRequiredError as err:
    await context.send_activity(
        f"Before I can help, please set up the required connections for "
        f"{', '.join(err.server_names)}: {err.missing_connections_url}"
    )
    return  # Skip running the model/tools this turn.
```

The gate fires only for gateway responses with aggregate `connectivityStatus == "Pending"`.
Dev-mode manifests and legacy raw-array responses omit the field and are never gated.
````

- [ ] **Step 3: Lint and format the whole change set**

Run: `uv run --frozen ruff check .`
Expected: no errors (fix any reported with `uv run --frozen ruff check . --fix`).

Run: `uv run --frozen ruff format .`
Expected: files formatted (or "X files left unchanged").

- [ ] **Step 4: Run the full tooling test suite once more**

Run: `uv run --frozen pytest tests/tooling/ -v -m "not integration"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libraries/microsoft-agents-a365-tooling/CHANGELOG.md libraries/microsoft-agents-a365-tooling/docs/design.md
git commit -m "docs(tooling): document MCP connection gating

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final verification

- [ ] Run lint: `uv run --frozen ruff check .` → no errors.
- [ ] Run format check: `uv run --frozen ruff format --check .` → clean.
- [ ] Run tooling tests: `uv run --frozen pytest tests/tooling/ -v -m "not integration"` → all pass.
- [ ] Confirm `McpConnectionsRequiredError` importable: `uv run --frozen python -c "from microsoft_agents_a365.tooling import McpConnectionsRequiredError; print('ok')"` → prints `ok`.

## Notes on scope

- Framework tooling extensions (`openai`, `semantickernel`, `agentframework`,
  `googleadk`, `azureaifoundry`) require **no code change**: their
  `add_tool_servers_to_agent` calls `list_tool_servers` and does not catch the new
  exception, so it propagates to the turn handler as designed.
- No poll/wait loop is implemented — per-turn discovery (no caching) provides the retry
  loop naturally.

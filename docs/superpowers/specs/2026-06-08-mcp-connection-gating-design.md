# MCP Connection-Gated Tool Discovery — Design

**Date:** 2026-06-08
**Status:** Proposed
**Package(s):** `microsoft-agents-a365-tooling` (core); framework tooling extensions inherit behavior.

## Problem

The tooling gateway discovery response for MCP servers has gained connection-state
fields. A server may be configured for an agent but not yet have its required
downstream connections (e.g. a Salesforce or Zendesk connector) established by the
user. If the agent runs tools against such a server, calls fail at execution time.

The runtime calls discovery on **every turn** when spinning up tools (there is no
caching of the server list — discovery re-runs each time `list_tool_servers` is
invoked). We want to use that per-turn discovery to **gate agent execution**: until
all required connections are present, the turn must not proceed. Instead the agent
should reply to the user with a link to set up the missing connections, and a later
turn (after the user connects) proceeds normally.

## New Schema

The wrapped gateway response now carries connection metadata at **two levels** —
per-server and response-level (aggregate):

```json
{
  "mcpServers": [
    {
      "mcpServerName": "mcp_Salesforce",
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "publisher": "Microsoft",
      "url": "https://agent365.svc.cloud.dev.microsoft/agents/v2/servers/mcp_Salesforce",
      "scope": "McpServers.Salesforce.All",
      "audience": "",
      "allConnectionsUrl": "<allConnectionsUrl>",
      "missingConnectionsUrl": "<missingConnectionsUrl>",
      "connectivityStatus": "<connectivityStatus>"
    }
  ],
  "allConnectionsUrl": "<allConnectionsUrl>",
  "missingConnectionsUrl": "<missingConnectionsUrl>",
  "connectivityStatus": "<connectivityStatus>"
}
```

Notes:
- The **response-level** `connectivityStatus` / `missingConnectionsUrl` /
  `allConnectionsUrl` are the authoritative aggregate signal used for gating and for
  the single "fix everything" link surfaced to the user.
- The **per-server** copies are parsed and retained for diagnostics only; they do not
  drive the gate decision.
- Key casing has been observed as both `connectivityStatus` and `ConnectivityStatus`.
  Parsing is tolerant of known key-name variants. **Open item:** confirm the exact
  JSON key casing with the gateway team and tighten if possible.

## Compatibility Rules

| Source | Aggregate `connectivityStatus` | Gate behavior |
|---|---|---|
| V2 gateway, all connections satisfied | `"Ready"` | proceeds |
| V2 gateway, missing connections | `"Pending"` | **blocks**, raises exception |
| Legacy raw-array gateway response | absent → `None` | proceeds (not gated) |
| Dev mode (`ToolingManifest.json`) | absent → `None` | proceeds (not gated) |

The gateway only ever emits `"Ready"` or `"Pending"` for `connectivityStatus` — never
`null` and never any other value. Sources that predate the field (legacy raw-array
responses, dev-mode manifests) omit it entirely, yielding `None`.

**Gate rule:** block only when the aggregate `connectivity_status` is **present and
not equal to** `"Ready"` (i.e. `"Pending"`). Absent status (`None`) is always treated
as ready, so dev mode and legacy callers are unaffected. The `!= "Ready"` form (rather
than `== "Pending"`) is deliberately defensive against any unexpected future value.

## Design

### 1. Model — `MCPServerConfig`

Add four optional fields (all default `None`, preserving existing constructor calls):

- `id: Optional[str]`
- `all_connections_url: Optional[str]`
- `missing_connections_url: Optional[str]`
- `connectivity_status: Optional[str]`

These hold the **per-server** values. No validation change.

### 2. Internal discovery result — `McpDiscoveryResult`

New internal dataclass (not part of the public return type) to carry response-level
aggregate metadata alongside the parsed servers:

```python
@dataclass
class McpDiscoveryResult:
    servers: List[MCPServerConfig]
    all_connections_url: Optional[str] = None
    missing_connections_url: Optional[str] = None
    connectivity_status: Optional[str] = None
```

### 3. Parsing changes

- `_parse_server_config` reads `id`, `allConnectionsUrl`, `missingConnectionsUrl`,
  `connectivityStatus` (tolerant casing) onto each `MCPServerConfig`. Gateway and
  manifest share this path; manifest entries simply lack the fields → `None`.
- `_parse_gateway_response` returns `McpDiscoveryResult`: it parses the server list as
  today and additionally extracts the **response-level** aggregate fields when the
  wrapped `{"mcpServers": [...]}` shape is present. The legacy raw-array shape yields a
  result with aggregate fields = `None`.
- `_load_servers_from_gateway` returns `McpDiscoveryResult`.
- The manifest/dev path wraps its server list in a `McpDiscoveryResult` with aggregate
  fields = `None`.

### 4. Readiness gate — core `list_tool_servers`

After discovery and per-audience token attachment, evaluate the aggregate status:

```python
if (result.connectivity_status is not None
        and result.connectivity_status != "Ready"):
    not_ready = [s for s in result.servers
                 if s.connectivity_status is not None
                 and s.connectivity_status != "Ready"]
    raise McpConnectionsRequiredError(
        missing_connections_url=result.missing_connections_url,
        all_connections_url=result.all_connections_url,
        connectivity_status=result.connectivity_status,
        server_names=[s.mcp_server_name or s.mcp_server_unique_name
                      for s in not_ready],
    )
```

The public return type of `list_tool_servers` remains `List[MCPServerConfig]`
(`result.servers`). The gate is the only new externally observable behavior, and only
fires for gateway responses reporting `connectivityStatus: "Pending"`.

### 5. Exception — `McpConnectionsRequiredError`

New exception type in the tooling package, exported from
`microsoft_agents_a365.tooling`:

```python
class McpConnectionsRequiredError(Exception):
    def __init__(
        self,
        missing_connections_url: Optional[str],
        all_connections_url: Optional[str],
        connectivity_status: Optional[str],
        server_names: List[str],
    ) -> None:
        ...
```

Exposes (per design decision) the **response-level** aggregate links plus the list of
not-`Ready` server names for context:
- `missing_connections_url` — single aggregate link to set up missing connections
  (primary value the handler surfaces to the user).
- `all_connections_url` — aggregate link to view/manage all connections.
- `connectivity_status` — the aggregate status that triggered the block (`"Pending"`).
- `server_names` — names of servers that are not yet `Ready`.

The `__str__`/message includes the missing-connections URL and server names so logs
are actionable.

### 6. Per-turn behavior & propagation

- No poll loop. Discovery already runs every turn (no list caching), so each turn
  re-hits the gateway. Once the user completes the connections, a subsequent turn
  passes the gate.
- Framework tooling extensions (`add_tool_servers_to_agent` in openai,
  semantickernel, agentframework, googleadk, azureaifoundry) **do not catch**
  `McpConnectionsRequiredError` — they let it propagate.
- The **agent's turn handler** (application code) catches it, replies to the user with
  the `missing_connections_url`, and returns without running the model/tools. This
  reply formatting is application responsibility; the SDK only signals and supplies the
  URLs. Documentation/sample will show the recommended catch-and-reply pattern.

## Out of Scope (YAGNI)

- Polling / blocking wait loops within a turn.
- Partial execution with only the connected servers (decision: block entirely on any
  unsatisfied aggregate status).
- The SDK itself sending the connection-setup reply (left to the turn handler).
- Caching discovery results across turns.

## Testing

- **Parser:** per-server new fields populated from a V2 element; absent in manifest
  element → `None`. Tolerant casing variants map to the same field.
- **Aggregate parsing:** `_parse_gateway_response` extracts response-level fields for
  wrapped shape; raw-array shape → aggregate `None`.
- **Gate fires:** aggregate `connectivity_status == "Pending"` raises
  `McpConnectionsRequiredError` carrying the correct response-level URLs and the
  not-Ready server names.
- **Gate passes:** aggregate `"Ready"`; aggregate absent (dev manifest); legacy
  raw array.
- **Exception payload:** `missing_connections_url` / `all_connections_url` /
  `connectivity_status` / `server_names` correct; message string actionable.
- **Propagation:** extension `add_tool_servers_to_agent` does not swallow the exception
  (it surfaces to the caller).

## Affected Files

- `libraries/microsoft-agents-a365-tooling/.../models/mcp_server_config.py` — new fields.
- `libraries/microsoft-agents-a365-tooling/.../models/__init__.py` — export
  `McpDiscoveryResult` if placed in models (or keep internal to the service module).
- `libraries/microsoft-agents-a365-tooling/.../services/mcp_tool_server_configuration_service.py`
  — parsing + gate.
- `libraries/microsoft-agents-a365-tooling/.../exceptions.py` (new) —
  `McpConnectionsRequiredError`.
- `libraries/microsoft-agents-a365-tooling/.../__init__.py` — export exception.
- `tests/tooling/...` — parser, gate, exception tests.
- `libraries/microsoft-agents-a365-tooling/CHANGELOG.md` — changelog entry.
- Tooling extension docs/samples — catch-and-reply pattern (follow-up).

## Open Items

1. Confirm exact JSON key casing for `connectivityStatus` (response and server level).
2. Confirmed: `connectivityStatus` is always `"Ready"` or `"Pending"` (never `null` or
   other values) from the V2 gateway. Field is absent only from legacy raw-array
   responses and dev-mode manifests.

# Tooling - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-tooling` package.

## Overview

The tooling package provides MCP (Model Context Protocol) tool server configuration and discovery services. It enables agents to dynamically discover and connect to tool servers for extending agent capabilities. It also provides the client for Microsoft Defender for AI real-time protection (see [Defender Real-Time Protection](#defender-real-time-protection-protectiondefender)).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Public API                                │
│  McpToolServerConfigurationService | MCPServerConfig            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              McpToolServerConfigurationService                   │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │   Development Mode   │    │   Production Mode   │            │
│  │                     │    │                     │            │
│  │ ToolingManifest.json│    │  Tooling Gateway    │            │
│  │    (local file)     │    │   (HTTP endpoint)   │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCPServerConfig[]                            │
│  { mcp_server_name, mcp_server_unique_name (URL) }              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### McpToolServerConfigurationService ([services/mcp_tool_server_configuration_service.py](../microsoft_agents_a365/tooling/services/mcp_tool_server_configuration_service.py))

The main service for discovering and configuring MCP tool servers.

```python
from microsoft_agents_a365.tooling import McpToolServerConfigurationService, MCPServerConfig

service = McpToolServerConfigurationService()

# Discover tool servers
servers = await service.list_tool_servers(
    agentic_app_id="app-id-123",
    auth_token="Bearer token",
    options=ToolOptions(orchestrator_name="LangChain")
)

for server in servers:
    print(f"Name: {server.mcp_server_name}")
    print(f"URL: {server.mcp_server_unique_name}")
```

#### Environment Detection

The service automatically selects the configuration source based on the `ENVIRONMENT` variable:

| Environment | Source | Description |
|-------------|--------|-------------|
| `Development` | `ToolingManifest.json` | Local file-based configuration |
| Other (default) | Tooling Gateway | HTTP endpoint discovery |

```python
# Set environment for development mode
os.environ["ENVIRONMENT"] = "Development"
```

#### Development Mode: Manifest-Based Configuration

In development mode, the service reads from `ToolingManifest.json`:

```json
{
  "mcpServers": [
    {
      "mcpServerName": "mailMCPServer",
      "mcpServerUniqueName": "mcp_MailTools"
    },
    {
      "mcpServerName": "sharePointMCPServer",
      "mcpServerUniqueName": "mcp_SharePointTools"
    }
  ]
}
```

**Search locations for manifest file:**
1. Current working directory
2. Parent directory
3. Project root (relative to package location)

The `mcpServerUniqueName` is transformed into a full URL using `build_mcp_server_url()`.

#### Production Mode: Gateway-Based Configuration

In production mode, the service calls the tooling gateway endpoint:

```
GET https://{gateway}/mcp/servers?agentId={agentic_app_id}
Authorization: Bearer {auth_token}
User-Agent: Agent365SDK/0.1.0 (...)
```

The gateway returns the same JSON structure, but `mcpServerUniqueName` contains the full endpoint URL.

### MCPServerConfig ([models/mcp_server_config.py](../microsoft_agents_a365/tooling/models/mcp_server_config.py))

Data class representing an MCP server configuration:

```python
@dataclass
class MCPServerConfig:
    mcp_server_name: str       # Display name of the tool server
    mcp_server_unique_name: str  # Full URL endpoint for the MCP server
```

### Chat History Service

The service also provides functionality for sending chat history to threat protection platforms:

```python
from microsoft_agents_a365.tooling import McpToolServerConfigurationService
from microsoft_agents_a365.tooling.models import ChatHistoryMessage

service = McpToolServerConfigurationService()

# Send chat history for threat protection
result = await service.send_chat_history(
    turn_context=turn_context,
    chat_history_messages=[
        ChatHistoryMessage(role="user", content="Hello"),
        ChatHistoryMessage(role="assistant", content="Hi there!")
    ],
    options=ToolOptions(orchestrator_name="MyAgent")
)

if result.succeeded:
    print("Chat history sent successfully")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
```

**Required TurnContext properties:**
- `activity.conversation.id` - Conversation identifier
- `activity.id` - Message identifier
- `activity.text` - User message text

### Utility Functions ([utils/utility.py](../microsoft_agents_a365/tooling/utils/utility.py))

Helper functions for URL construction and endpoint discovery:

```python
from microsoft_agents_a365.tooling import (
    get_tooling_gateway_for_digital_worker,
    get_mcp_base_url,
    build_mcp_server_url,
)

# Get tooling gateway endpoint
gateway_url = get_tooling_gateway_for_digital_worker("app-id-123")

# Get MCP base URL from environment
base_url = get_mcp_base_url()

# Build full MCP server URL
full_url = build_mcp_server_url("mcp_MailTools")
```

### Constants ([utils/constants.py](../microsoft_agents_a365/tooling/utils/constants.py))

HTTP header constants:

```python
class Constants:
    class Headers:
        AUTHORIZATION = "Authorization"
        BEARER_PREFIX = "Bearer"
        USER_AGENT = "User-Agent"
```

## Data Models

### ToolOptions

```python
@dataclass
class ToolOptions:
    orchestrator_name: str | None = None  # Name for User-Agent header
```

### ChatHistoryMessage

```python
@dataclass
class ChatHistoryMessage:
    role: str      # "user", "assistant", or "system"
    content: str   # Message content
```

### ChatMessageRequest

```python
@dataclass
class ChatMessageRequest:
    conversation_id: str
    message_id: str
    user_message: str
    chat_history: List[ChatHistoryMessage]

    def to_dict(self) -> dict:
        # Serialization for HTTP request
```

## Design Patterns

### Strategy Pattern

The service uses the Strategy pattern to select between manifest-based and gateway-based configuration loading:

```python
def list_tool_servers(self, ...):
    if self._is_development_scenario():
        return self._load_servers_from_manifest()  # Strategy A
    else:
        return await self._load_servers_from_gateway(...)  # Strategy B
```

### Async/Await Pattern

Gateway communication uses async/await for non-blocking HTTP calls:

```python
async with aiohttp.ClientSession() as session:
    async with session.get(endpoint, headers=headers) as response:
        if response.status == 200:
            return await self._parse_gateway_response(response)
```

### Result Pattern

The `send_chat_history` method uses `OperationResult` from the runtime package:

```python
async def send_chat_history(self, ...) -> OperationResult:
    try:
        # Send request
        return OperationResult.success()
    except Exception as ex:
        return OperationResult.failed(OperationError(ex))
```

## Defender Real-Time Protection ([protection/defender/](../microsoft_agents_a365/tooling/protection/defender/))

Microsoft Defender for AI real-time protection (Defender RTP): the prevention endpoint
`POST .../v1/protection/evaluate` takes an agent-hooks/0.1 context and returns a verdict. This module has no
agent-hooks dependency; `microsoft-agents-a365-tooling-extensions-agenthooks` plugs it into an agent-hooks emitter.

| Class | Purpose |
|-------|---------|
| `DefenderRtpOptions` | Configuration; `from_environment()` reads the `A365_DEFENDER_RTP_*` variables |
| `DefenderRtpClient` | `evaluate_hook_context()`, `prefetch_access_token()`, `is_evaluated_interception_point()`, `unavailable()` |
| `DefenderRtpAgentContext` | The agent identity and turn; fills context fields the host did not set |
| `DefenderRtpTokenResolver` | `(agent_id, tenant_id, scopes) -> token`, sync or async |
| `DefenderRtpTokenResolvers` | `from_agentic_connection()`: the agent identity's app-only token through the agent's connection |
| `DefenderRtpEvaluationResult` | `allowed`, `evaluated`, `correlation_id`, `verdict`, `http_status`, `error`, `block_reason` |

```python
from microsoft_agents_a365.tooling.protection.defender import (
    DefenderRtpAgentContext,
    DefenderRtpClient,
    DefenderRtpOptions,
    DefenderRtpTokenResolvers,
)

client = DefenderRtpClient(DefenderRtpOptions.from_environment())
tokens = DefenderRtpTokenResolvers.from_agentic_connection(connection)
agent = DefenderRtpAgentContext(agent_id=agent_identity_id, tenant_id=tenant_id)

result = await client.evaluate_hook_context(context, agent, tokens)
if result is not None and not result.allowed:
    ...  # blocked: result.block_reason; Defender logs the call under result.correlation_id
```

**Evaluated points:** `input`, `pre_tool_call`, `post_tool_call` and `output`. Other points, and every point while
`enabled` is false, return `None` without a call.

**Request:** Defender receives a fitted copy of the context (the host's context is not modified): `spec` is
`agent-hooks/0.1` and the timestamp is UTC. A valid `sequence` the host set (an integer of at least 0) is sent
unchanged: the client does not repair the order of host values, so it is the host that keeps them increasing. A
missing or invalid one is generated above the highest sequence seen in the session, host values included; the client
tracks up to 1,000 sessions, and a session it no longer tracks continues above the highest sequence of every session it
dropped, so generated values never repeat or decrease within a session.
`agent.framework` is lowercased to `[a-z0-9_-]` (default `agent365`), `target` equals the point's field,
`tool_call` and `tool_result` keep only spec members (non-object tool arguments become `{"input": ...}`), and loosely
filled optional fields (`extensions`, `model`, `tools`, `messages`, `actor`, `request_id`, `trace`) are repaired or
dropped; `tool_call.content_hash` and `tool_result.duration_ms` are kept when they meet the spec. `tenant.id` is
always the agent's tenant, which the token is issued for and Defender requires; `agent.id`, `actor`, `request_id` and
`model.id` are filled from `DefenderRtpAgentContext` when the host did not set them (a `request_id` that is empty or
not a string counts as not set). The envelope (spec, timestamp,
sequence, agent, session, tenant, actor, request, model, trace, and roles, tool names and ids) is built from its spec
fields alone (`session` keeps `id`, a UTC `started_at` and a non-negative `turn`; `tenant` its `name`; `trace`
`trace_id` and `span_id`), so nothing else a host puts in an envelope object escapes the content budget, and it is
never cut, so the request validates and correlates whatever the limit. Content is cut to fit (see **Long content**), and every string
and key is sent as valid Unicode: split surrogate pairs are rejoined and lone surrogates become U+FFFD, since a lone
surrogate cannot be encoded and would otherwise keep the request from being sent. NaN and infinities are sent as
text. The copy is built from the context without copying it whole. Each call sends a unique `x-ms-correlation-id`. The
endpoint must be an absolute HTTPS URL, and redirects are not followed (a 3xx follows the fail mode); the client keeps
a private copy of its options, so later changes to the caller's object do not reach it.

**Authentication:** Defender is always called app-only as the agent identity. `from_agentic_connection` gets the
agent identity's assertion from the connection (`AccessTokenProviderBase.get_agentic_application_token`, implemented by
`MsalAuth`; hosting-core 0.8 and later pass the tenant, 0.4 to 0.7 do not) and exchanges it at
`https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` (`client_credentials` with a `jwt-bearer` client
assertion; the authority must be HTTPS, and a redirect is a token failure) for the Defender API scope. The client caches tokens per agent, tenant and
scope until they expire and shares one acquisition between concurrent calls; the acquisition is dropped when it
completes, and a failed one is never cached. Within five minutes of expiry, a call refreshes the token in the
background and keeps using the cached token, also when the refresh fails. A token resolver may be sync or async; a
synchronous one (for example one that calls MSAL directly) runs on a worker thread, so it never blocks the event loop
and the deadline applies while it waits. A timeout cannot stop that thread, so one call per agent, tenant and scope
runs at a time: a later acquisition waits for the same call, and a resolver that blocks cannot pile up threads.

**Deadline:** token acquisition and the request share one deadline, `timeout_seconds`, so the fail mode applies within
that time, before an agent-hooks interceptor timeout above it.

**Fail mode:** a timeout, transport failure (including any exception from the HTTP session other than the caller's
cancellation), token failure, non-2xx response, or a response without a verdict is not evaluated (`evaluated=False`,
with `error` and `http_status`) and is allowed, or blocked when `A365_DEFENDER_RTP_FAIL_MODE=closed`. A `400` reports
Defender's failed validation rules (`diagnostics.validationErrors`) in `error`. A `transform` verdict blocks, because
this SDK version does not apply it.

**Long content:** each content string is cut to at most `max_content_characters` characters, ending with a
`...[truncated N chars]` marker when it fits (N counts characters as sent, so a rejoined pair is one; a string that is
not ASCII and longer than the twice-the-limit prefix that is read gets `...[truncated]`, since counting the rest would
mean reading all of it), and all
content in one request shares a budget of four times that
(each string, key, number and kept-whole name counts its length, every other value one), so the request and the time
to prepare it stay bounded. The content under decision (`target`: the input, a tool call's arguments, a tool result,
or the output) is sent twice, as the point's field and as `target`, so it may use half of the budget. The rest goes, in
order, to the called tool's declaration (below), the call's arguments at `post_tool_call` (which Defender decided on at
`pre_tool_call`, so cutting them is not a truncation), the other tool declarations, the most recent messages,
extensions, and any other member; what does not fit is dropped. Message histories (newest first), extension namespaces
and the tool declarations other than the called tool's are read only as far as the budget reaches, so a long one costs
no more than what is sent. Containers nested deeper than 32 levels are cut too. When the content under decision is cut, Defender
evaluates a truncated copy and the result has `truncated=True`. A block (`deny` or `transform`) stays a block; an
allow does not cover the rest of the content, so `allowed` follows the fail mode, `error` says so, and `verified` is
false. Raising the limit is the remedy for long-content agents; chunked evaluation is a follow-up.

**The called tool's declaration:** at `pre_tool_call` and `post_tool_call`, Defender's verdict also depends on how the
called tool is declared. Its declaration is searched for by name among the first 10,000 entries of `tools` and copied
first, with its name whole, ahead of the call's arguments at `post_tool_call` and of the other declarations, which then
fill what is left of the budget in the host's order. The result has `truncated=True` too, and an allow follows the fail
mode, when the called tool's description or schema had to be cut, or when `tools` is longer than the entries searched
and the called tool is not among them (each with its own `error`). A list searched in full that does not declare the
called tool is not a truncation. When none of the entries searched declares a tool, the called tool is declared from
the `a365` extension's `tool.description`, which counts as its description.

**Unexpected shapes:** every optional node is shape-checked before it is read: a context member (for example a string
`model` or `a365` extension), a verdict member (`transform`, `warnings`, `result_labels`), a `400` body's
`diagnostics`, a token's payload and the token endpoint's response. One of an unexpected shape is ignored, so it never
turns Defender's verdict into an unavailable result.

## File Structure

```
microsoft_agents_a365/tooling/
├── __init__.py                           # Public API exports
├── models/
│   ├── __init__.py
│   ├── mcp_server_config.py              # MCPServerConfig dataclass
│   ├── tool_options.py                   # ToolOptions dataclass
│   ├── chat_history_message.py           # ChatHistoryMessage dataclass
│   └── chat_message_request.py           # ChatMessageRequest dataclass
├── protection/
│   ├── __init__.py
│   └── defender/                         # Defender real-time protection
│       ├── __init__.py
│       ├── defender_rtp_agent_context.py # DefenderRtpAgentContext, DefenderRtpTokenResolver
│       ├── defender_rtp_client.py        # DefenderRtpClient
│       ├── defender_rtp_evaluation_result.py
│       ├── defender_rtp_options.py       # DefenderRtpOptions
│       └── defender_rtp_token_resolvers.py
├── services/
│   ├── __init__.py
│   └── mcp_tool_server_configuration_service.py  # Main service
└── utils/
    ├── __init__.py
    ├── constants.py                       # HTTP header constants
    └── utility.py                         # URL construction utilities
```

## Environment Variables

| Variable | Purpose | Values |
|----------|---------|--------|
| `ENVIRONMENT` | Controls dev vs prod mode | `Development`, `Production` (default) |
| `MCP_BASE_URL` | Base URL for MCP servers (dev mode) | URL string |
| `ENABLE_A365_DEFENDER_RTP` | Enables Defender real-time protection | `true`, `1`, `yes`, `on`; `false`, `0`, `no`, `off`; default off; any other value is rejected |
| `A365_DEFENDER_RTP_ENDPOINT` | Defender prevention endpoint; required when enabled | `https://<host>/v1/protection/evaluate` |
| `A365_DEFENDER_RTP_FAIL_MODE` | Outcome when no verdict is obtained | `open` (default), `closed`; any other value is rejected |
| `A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS` | Per-call timeout for token acquisition and evaluation | Positive integer up to `2147483647`; default `10000` |
| `A365_DEFENDER_RTP_AUTHENTICATION_SCOPE` | Token scope | Default `api://86a21212-634e-4553-b3d6-e477e4c9d9ec/.default` |
| `A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS` | Maximum characters per content string; all content in a request shares four times that | Positive integer up to `2147483647`; default `20000` |

## Error Handling

The service provides detailed error messages for common failures:

```python
# Validation errors
ValueError("agentic_app_id cannot be empty or None")
ValueError("auth_token cannot be empty or None")

# HTTP errors
Exception(f"HTTP {status}: {response_text}")

# JSON parsing errors
Exception(f"Failed to parse MCP server configuration response: {error}")

# Connection errors
Exception(f"Failed to connect to MCP configuration endpoint: {error}")
```

## Testing

Tests are located in `tests/tooling/`:

```bash
# Run all tooling tests
pytest tests/tooling/ -v

# Run specific test
pytest tests/tooling/test_mcp_tool_server_configuration_service.py -v
```

## Dependencies

- `aiohttp` - Async HTTP client for gateway communication and Defender evaluation
- `microsoft-agents-hosting-core` - TurnContext type; `AccessTokenProviderBase` for Defender tokens
- `microsoft-agents-a365-runtime` - OperationResult, Utility

## Integration with Framework Extensions

The tooling package is extended by framework-specific packages:

| Extension Package | Purpose |
|-------------------|---------|
| `tooling-extensions-agentframework` | Microsoft Agents SDK integration |
| `tooling-extensions-agenthooks` | Defender real-time protection as an agent-hooks interceptor |
| `tooling-extensions-azureaifoundry` | Azure AI Foundry integration |
| `tooling-extensions-openai` | OpenAI function calling integration |
| `tooling-extensions-semantickernel` | Semantic Kernel plugin integration |

These extensions adapt the `MCPServerConfig` objects to framework-specific tool definitions; the agent-hooks extension
adapts `DefenderRtpClient` to the agent-hooks interceptor contract.
